"""dagster_runs: the read-only "why did this Dagster run fail?" diagnostic (B239, docs/runbooks/dagster.md).

It runs inside the dagster-user-code pod (`kubectl exec -i ... -- python3 - < scripts/lib/dagster_runs.py`), so it is
one stdlib file. These tests pin the decisions it makes: input validation (values are interpolated into GraphQL, so
anything but a plain job name or run id is refused), and how events become the lines an operator reads. The event
shapes are copied from a real run observed 2026-11-08 (datahub_catalog_emit_job, run 6a6f3d61).
"""
import pytest

import dagster_runs as dr


def test_runs_query_filters_failures_and_optionally_one_job():
    q = dr.runs_query(job=None, limit=5)
    assert "statuses:[FAILURE]" in q and "limit:5" in q and "pipelineName" not in q
    q = dr.runs_query(job="datahub_catalog_emit_job", limit=3)
    assert 'pipelineName:"datahub_catalog_emit_job"' in q and "limit:3" in q


@pytest.mark.parametrize("bad", ['x"}){a', "job name", "", "a" * 200])
def test_job_names_that_could_break_the_query_are_refused(bad):
    with pytest.raises(ValueError, match="job"):
        dr.runs_query(job=bad, limit=5)


@pytest.mark.parametrize("bad", ["6a6f3d61", 'abc"}', "", "zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz"])
def test_run_ids_must_be_full_uuids(bad):
    with pytest.raises(ValueError, match="run id"):
        dr.run_query(bad)


def test_limit_is_bounded():
    with pytest.raises(ValueError, match="limit"):
        dr.runs_query(job=None, limit=0)
    with pytest.raises(ValueError, match="limit"):
        dr.runs_query(job=None, limit=500)


REAL_EVENTS = [
    {"__typename": "RunStartEvent"},
    {"__typename": "ExecutionStepStartEvent"},
    {"__typename": "ExecutionStepFailureEvent", "stepKey": "emit_tag_assignments_op",
     "error": {"message": "dagster._core.errors.DagsterExecutionInterruptedError\n"}},
    {"__typename": "RunFailureEvent", "message": "Exceeded maximum runtime of 1800 seconds."},
]


def test_failure_events_become_readable_lines_in_order():
    assert dr.failure_lines(REAL_EVENTS) == [
        "step failed: emit_tag_assignments_op: dagster._core.errors.DagsterExecutionInterruptedError",
        "run failed: Exceeded maximum runtime of 1800 seconds.",
    ]


def test_a_run_with_no_failure_events_says_so():
    # A run killed from outside (pod OOM, eviction) can end FAILURE with no failure event: point at the pod logs.
    lines = dr.failure_lines([{"__typename": "RunStartEvent"}])
    assert len(lines) == 1 and "no failure event" in lines[0] and "kubectl" in lines[0]


def test_long_messages_are_cut_to_one_line():
    ev = [{"__typename": "ExecutionStepFailureEvent", "stepKey": "s", "error": {"message": "a\nb" + "x" * 1000}}]
    (line,) = dr.failure_lines(ev)
    assert "\n" not in line and len(line) < 450


HEALTH = {  # shape observed 2026-11-08
    "instance": {"daemonHealth": {"allDaemonStatuses": [
        {"daemonType": "SCHEDULER", "healthy": True, "required": True},
        {"daemonType": "SENSOR", "healthy": False, "required": True},
        {"daemonType": "BACKFILL", "healthy": False, "required": False}]}},
    "workspaceOrError": {"__typename": "Workspace", "locationEntries": [
        {"name": "weyland_pipeline", "loadStatus": "LOADED", "locationOrLoadError": {"__typename": "RepositoryLocation"}}]},
}


def test_health_flags_an_unhealthy_required_daemon_and_ignores_optional_ones():
    lines, ok = dr.health_lines(HEALTH)
    assert not ok
    assert "UNHEALTHY daemon SENSOR" in lines
    assert not any("BACKFILL" in ln for ln in lines if "UNHEALTHY" in ln)
    assert "code location weyland_pipeline: LOADED" in lines


def test_health_flags_a_code_location_that_failed_to_load():
    data = {"instance": {"daemonHealth": {"allDaemonStatuses": []}},
            "workspaceOrError": {"__typename": "Workspace", "locationEntries": [
                {"name": "weyland_pipeline", "loadStatus": "LOADED",
                 "locationOrLoadError": {"__typename": "PythonError", "message": "ImportError: no module x"}}]}}
    lines, ok = dr.health_lines(data)
    assert not ok
    assert any("FAILED TO LOAD" in ln and "ImportError" in ln for ln in lines)


def test_health_with_no_daemons_reported_is_not_healthy():
    # Fail closed: an empty status list means the daemon is not heartbeating, not that all is well.
    data = {"instance": {"daemonHealth": {"allDaemonStatuses": []}},
            "workspaceOrError": {"__typename": "Workspace", "locationEntries": []}}
    lines, ok = dr.health_lines(data)
    assert not ok


def test_run_rows_show_short_id_job_and_utc_start():
    rows = dr.run_rows([{"runId": "6a6f3d61-0000-4000-8000-000000000000", "jobName": "datahub_catalog_emit_job",
                         "status": "FAILURE", "startTime": 1794116110.25}])
    assert rows == ["6a6f3d61-0000-4000-8000-000000000000  2026-11-08 05:35 UTC  datahub_catalog_emit_job"]
