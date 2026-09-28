"""Tests for datahub_ingestion_check.py — the B197 DataHub ingestion watchdog.

What these pin down are the DECISIONS: which source gets which alert (failed / stale / never ran), how a schedule
becomes a budget, which sources are accepted as on-demand, and when the watchdog must refuse to answer (exit 2) rather
than report a clean catalog it could not read. The GraphQL response shapes are copied from a real
`listIngestionSources { executions }` query against the lab's GMS (2026-09-28).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/ on path

import datahub_ingestion_check as dh

NOW = 1790600000.0  # 2026-09-28T...Z — a fixed clock
H = 3600


def _run(status, ago_s):
    return {"id": f"x{ago_s}", "input": {"requestedAt": int((NOW - ago_s) * 1000)},
            "result": {"status": status, "startTimeMs": int((NOW - ago_s) * 1000), "durationMs": 1000}}


def _src(name, cron="0 1 * * *", tz="America/New_York", runs=None, urn=None):
    return {"urn": urn or f"urn:li:dataHubIngestionSource:{name}", "name": name, "type": "postgres",
            "schedule": {"interval": cron, "timezone": tz} if cron else None,
            "executions": {"executionRequests": runs if runs is not None else [_run("SUCCESS", 6 * H)]}}


def _page(sources, total=None):
    return {"data": {"listIngestionSources": {"total": len(sources) if total is None else total,
                                              "ingestionSources": sources}}}


# --- schedule → budget ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("cron,period", [
    ("0 1 * * *", 86400), ("30 4 * * 0", 604800), ("*/15 * * * *", 900), ("4 5 * * *", 86400),
])
def test_known_schedule_shapes_have_a_period(cron, period):
    assert dh.period_seconds(cron) == period


@pytest.mark.parametrize("cron", ["0 1 1 * *", "0 1 * 6 *", "garbage", ""])
def test_an_unmodelled_schedule_is_refused_not_guessed(cron):
    with pytest.raises(dh.CannotRead):
        dh.period_seconds(cron)


def test_the_budget_is_twice_the_period_with_a_one_hour_floor():
    assert dh.budget_seconds(86400) == 2 * 86400
    assert dh.budget_seconds(900) == H  # 2 x 15m = 30m, floored so a 15-minute source cannot flap


# --- per-source verdicts -------------------------------------------------------------------------------------------

def test_a_healthy_daily_source_fires_nothing():
    assert dh.verdicts([_src("Postgres - Weyland")], NOW) == []


def test_a_latest_failure_fires_failed_naming_the_source():
    v = dh.verdicts([_src("dbt - Weyland", runs=[_run("FAILURE", H), _run("SUCCESS", 25 * H)])], NOW)
    assert [(a, s) for a, s, _ in v] == [("DataHubIngestionFailed", "dbt - Weyland")]


def test_aborted_counts_as_failed():
    v = dh.verdicts([_src("x", runs=[_run("ABORTED", H), _run("SUCCESS", 20 * H)])], NOW)
    assert v[0][0] == "DataHubIngestionFailed"


def test_no_success_inside_the_budget_fires_stale():
    v = dh.verdicts([_src("MLFlow - Weyland", runs=[_run("SUCCESS", 3 * 86400)])], NOW)
    assert [(a, s) for a, s, _ in v] == [("DataHubIngestionStale", "MLFlow - Weyland")]


def test_a_run_stuck_running_does_not_count_as_success():
    # An actions-pod restart orphaned runs in RUNNING (seen 2026-09-27): the latest run is not a failure, but it is
    # not a success either, so the budget still runs out.
    v = dh.verdicts([_src("x", runs=[_run("RUNNING", 60 * H), _run("SUCCESS", 70 * H)])], NOW)
    assert [a for a, _, _ in v] == ["DataHubIngestionStale"]


def test_cancelled_is_not_success_and_not_failure():
    v = dh.verdicts([_src("x", runs=[_run("CANCELLED", H), _run("SUCCESS", 2 * H)])], NOW)
    assert v == []


def test_a_scheduled_source_that_never_ran_fires_never_ran():
    v = dh.verdicts([_src("New - Weyland", runs=[])], NOW)
    assert [(a, s) for a, s, _ in v] == [("DataHubIngestionNeverRan", "New - Weyland")]


def test_runs_are_ordered_by_time_not_by_response_order():
    v = dh.verdicts([_src("x", runs=[_run("SUCCESS", 2 * H), _run("FAILURE", H)])], NOW)
    assert v[0][0] == "DataHubIngestionFailed"


def test_the_accepted_on_demand_cli_source_is_skipped():
    cli = _src("[CLI] dbt", cron=None, runs=[_run("SUCCESS", 80 * 86400)],
               urn="urn:li:dataHubIngestionSource:cli-151c2b7711eb626e440af8c75a9082e9")
    assert dh.verdicts([cli], NOW) == []


def test_an_unscheduled_source_that_is_not_accepted_fires_stale():
    v = dh.verdicts([_src("Someone's UI source", cron=None, runs=[_run("SUCCESS", H)])], NOW)
    assert v[0][0] == "DataHubIngestionStale" and "no schedule" in v[0][2]


def test_budget_factor_and_only_narrow_a_drill_to_one_source():
    srcs = [_src("Postgres - Weyland"), _src("Trino - Weyland")]
    v = dh.verdicts(srcs, NOW, factor=0.0001, only="Trino - Weyland")
    assert [(a, s) for a, s, _ in v] == [("DataHubIngestionStale", "Trino - Weyland")]


# --- reading GMS ---------------------------------------------------------------------------------------------------

def test_list_sources_returns_every_source():
    got = dh.list_sources(lambda q, v: _page([_src("a"), _src("b")]))
    assert [s["name"] for s in got] == ["a", "b"]


def test_list_sources_pages_until_total():
    pages = [_page([_src("a")], total=2), _page([_src("b")], total=2)]
    got = dh.list_sources(lambda q, v: pages[v["start"]])
    assert [s["name"] for s in got] == ["a", "b"]


def test_an_empty_source_list_refuses():
    with pytest.raises(dh.CannotRead):
        dh.list_sources(lambda q, v: _page([]))


def test_graphql_errors_refuse_even_on_http_200():
    with pytest.raises(dh.CannotRead):
        dh.list_sources(lambda q, v: {"errors": [{"message": "Unauthorized"}]})


def test_a_short_page_that_claims_more_refuses():
    with pytest.raises(dh.CannotRead):
        dh.list_sources(lambda q, v: _page([], total=5) if v["start"] else _page([_src("a")], total=5))


# --- alert payload + main ------------------------------------------------------------------------------------------

def test_the_alert_payload_names_the_source():
    body = dh.alert_payload("DataHubIngestionFailed", "dbt - Weyland", "latest run FAILURE")
    assert body[0]["labels"]["alertname"] == "DataHubIngestionFailed"
    assert body[0]["labels"]["ingestion_source"] == "dbt - Weyland"
    assert body[0]["labels"]["source"] == "datahub-ingestion-watchdog"
    assert "dbt - Weyland" in body[0]["annotations"]["summary"]


def test_main_without_endpoints_is_2(monkeypatch, capsys):
    for k in ("DATAHUB_GMS_URL", "DATAHUB_GMS_TOKEN", "ALERTMANAGER_URL"):
        monkeypatch.delenv(k, raising=False)
    assert dh.main([]) == 2
    assert "DATAHUB_GMS_URL" in capsys.readouterr().err


def test_main_fires_one_post_per_verdict_and_exits_0(monkeypatch):
    posted = []
    monkeypatch.setattr(dh, "_gms", lambda url, token: lambda q, v: _page(
        [_src("ok"), _src("bad", runs=[_run("FAILURE", H)])]))
    monkeypatch.setattr(dh, "_post_alert", lambda url, body: posted.append(body))
    rc = dh.main(["--gms", "http://gms", "--alertmanager", "http://am", "--token", "t"])
    assert rc == 0
    assert [b[0]["labels"]["ingestion_source"] for b in posted] == ["bad"]


def test_main_is_1_when_an_alert_cannot_be_delivered(monkeypatch):
    # An alert that fails to POST is a watchdog that did not watch: fail the Job so ScheduledJobFailed pages instead.
    def boom(url, body):
        raise OSError("connection refused")
    monkeypatch.setattr(dh, "_gms", lambda url, token: lambda q, v: _page([_src("bad", runs=[_run("FAILURE", H)])]))
    monkeypatch.setattr(dh, "_post_alert", boom)
    assert dh.main(["--gms", "http://gms", "--alertmanager", "http://am", "--token", "t"]) == 1
