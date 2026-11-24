"""B243: scripts/lib/dagster_reexecute.py, the one Dagster mutation the morning runner may make (allowlist action
dagster-reexecute-run). It re-executes ONE failed run from its failure, tagged so the report can tell a run the agent
started from a real fault. The mutation shape was read from this Dagster's own schema (introspection, 2026-11-24):
launchRunReexecution(reexecutionParams: {parentRunId, strategy: FROM_FAILURE, extraTags}).
"""
import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("dagster_reexecute", ROOT / "scripts" / "lib" / "dagster_reexecute.py")
dr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dr)
RUN = "0f8e7d6c-1234-4abc-9def-0123456789ab"


def test_the_mutation_reexecutes_from_failure_and_tags_the_new_run():
    body = dr.mutation_body(RUN)
    variables = body["variables"]["params"]
    assert variables["parentRunId"] == RUN and variables["strategy"] == "FROM_FAILURE"
    assert {"key": "weyland/started-by", "value": "morning-remediation"} in variables["extraTags"]
    assert "launchRunReexecution" in body["query"]


def test_a_launched_run_is_success_and_names_the_new_run():
    ok, msg = dr.outcome({"data": {"launchRunReexecution": {"__typename": "LaunchRunSuccess",
                                                            "run": {"runId": "new-1"}}}})
    assert ok and "new-1" in msg


def test_any_other_answer_is_a_failure_with_its_reason():
    ok, msg = dr.outcome({"data": {"launchRunReexecution": {"__typename": "PythonError", "message": "boom"}}})
    assert not ok and "PythonError" in msg and "boom" in msg
    ok, msg = dr.outcome({"errors": [{"message": "bad query"}]})
    assert not ok and "bad query" in msg


def test_a_malformed_run_id_is_refused_before_anything_is_sent():
    with pytest.raises(SystemExit) as stop:
        dr.main(["--run", "x; drop"])
    assert stop.value.code == 2


def test_status_reads_one_runs_status_with_a_query_never_a_mutation():
    q = dr.status_body(RUN)["query"]
    assert "mutation" not in q and "runOrError" in q and RUN in dr.status_body(RUN)["variables"]["id"]
    assert dr.status_of({"data": {"runOrError": {"__typename": "Run", "status": "SUCCESS"}}}) == "SUCCESS"
    assert dr.status_of({"data": {"runOrError": {"__typename": "RunNotFoundError"}}}) == "NOT_FOUND"
