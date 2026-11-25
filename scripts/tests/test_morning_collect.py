"""B243: scripts/lib/morning_collect.py, the read-only morning collection of what broke overnight.

Each source's parser is pure and tested here against fixtures shaped like the real responses observed on 2026-11-24:
Woodpecker's pipeline detail (workflows -> children with state; `killed` steps are fallout, `failure` steps are
causes) and its log entries (base64 `data`, which can be null); Prometheus `ALERTS` series; GitHub Dependabot alerts;
dagster_runs.py --json-since rows; GlitchTip issue rows from its Django shell; Linear Auto-Filed incidents. A source that
cannot be read is reported as NOT CHECKED, never as "nothing broke", and evidence is scrubbed of secret-shaped text.
"""
import base64
import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("morning_collect", ROOT / "scripts" / "lib" / "morning_collect.py")
mc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mc)

SINCE = 1000


def _b64(text):
    return base64.b64encode(text.encode()).decode()


# --- Woodpecker ---------------------------------------------------------------------------------------------------
PIPELINE = {"number": 718, "event": "cron", "status": "failure", "created": 2000, "forge_url": "https://x/718",
            "workflows": [
                {"name": "deliver", "children": [{"id": 1, "name": "build", "state": "killed", "exit_code": 0}]},
                {"name": "platform", "children": [{"id": 2, "name": "shellcheck", "state": "failure", "exit_code": 1},
                                                   {"id": 3, "name": "lint", "state": "success", "exit_code": 0}]}]}


def test_a_failed_ci_step_is_one_failure_and_killed_steps_are_not_causes():
    logs = {2: [{"data": _b64("In scripts/x.sh line 18:")}, {"data": None}, {"data": _b64("SC1090 (warning)")}]}
    out = mc.parse_woodpecker([PIPELINE], logs, since=SINCE)
    assert [f.key for f in out] == ["ci:platform/shellcheck"]
    f = out[0]
    assert f.source == "ci" and "718" in f.title and "cron" in f.title and "SC1090" in f.evidence
    assert f.extra == {"pipeline": 718, "event": "cron", "step_id": 2, "nightly": True}


def test_pipelines_before_the_window_or_green_are_ignored():
    old = {**PIPELINE, "created": 10}
    green = {**PIPELINE, "status": "success"}
    assert mc.parse_woodpecker([old, green], {}, since=SINCE) == []


# --- Prometheus alerts ----------------------------------------------------------------------------------------------
def test_relevant_alerts_become_failures_and_noise_is_dropped():
    series = [{"metric": {"alertname": "InfoInhibitor", "severity": "none"}},
              {"metric": {"alertname": "Watchdog", "severity": "none"}},
              {"metric": {"alertname": "KubeJobFailed", "severity": "warning", "namespace": "weyland",
                          "job_name": "pr-staleness-check-29920965"}},
              {"metric": {"alertname": "ScheduledJobFailed", "severity": "warning", "namespace": "weyland",
                          "cronjob": "pr-staleness-check"}},
              {"metric": {"alertname": "NodeDiskFull", "severity": "critical", "instance": "mother"}},
              {"metric": {"alertname": "SomethingMinor", "severity": "warning"}}]
    keys = sorted(f.key for f in mc.parse_alerts(series))
    # The scheduled-job family names the per-run Job (pr-staleness-check-29400); the cause is the CronJob, so all of
    # them merge into one item per CronJob (live 2026-11-24: one failing CronJob had produced seven items).
    assert keys == ["alert:NodeDiskFull:mother", "cronjob:weyland/pr-staleness-check",
                    "cronjob:weyland/pr-staleness-check"]
    failures, _ = mc.collect(0, {"alerts": lambda _s: mc.parse_alerts(series)})
    job = next(f for f in failures if f.key == "cronjob:weyland/pr-staleness-check")
    assert job.extra["namespace"] == "weyland" and job.extra["cronjob"] == "pr-staleness-check"
    assert "KubeJobFailed" in job.evidence and "ScheduledJobFailed" in job.evidence


# --- Dependabot -----------------------------------------------------------------------------------------------------
def test_only_new_high_or_critical_dependabot_alerts_count():
    alerts = [{"number": 1, "created_at": "2026-11-24T01:00:00Z", "html_url": "u1",
               "security_advisory": {"severity": "critical", "summary": "RCE"}, "dependency": {"package": {"name": "a"}}},
              {"number": 2, "created_at": "2026-11-24T01:00:00Z", "html_url": "u2",
               "security_advisory": {"severity": "medium", "summary": "x"}, "dependency": {"package": {"name": "b"}}},
              {"number": 3, "created_at": "2020-01-01T00:00:00Z", "html_url": "u3",
               "security_advisory": {"severity": "high", "summary": "old"}, "dependency": {"package": {"name": "c"}}}]
    out = mc.parse_dependabot("weyland-lab", alerts, since=mc.iso_to_epoch("2026-11-23T12:00:00Z"))
    assert [f.key for f in out] == ["dependabot:weyland-lab/a"] and "critical" in out[0].title


# --- Dagster, GlitchTip, Linear ---------------------------------------------------------------------------------------
def test_dagster_rows_become_failures_marked_when_the_agent_started_them():
    rows = [{"runId": "r1", "jobName": "emit_job", "endTime": 2000, "started_by_agent": False,
             "failures": ["step x: boom"]},
            {"runId": "r2", "jobName": "emit_job", "endTime": 2100, "started_by_agent": True, "failures": []}]
    out = mc.parse_dagster(rows)
    assert [f.key for f in out] == ["dagster:emit_job", "dagster:emit_job"]
    assert out[0].extra["run_id"] == "r1" and out[1].agent_caused is True and "boom" in out[0].evidence


def test_glitchtip_issues_seen_in_the_window_and_unresolved_count_new_ones_marked():
    rows = [{"id": 7, "short_id": "API-7", "title": "KeyError: x", "culprit": "app.views", "level": "error",
             "status": "unresolved", "first_seen": 1500, "last_seen": 1800, "count": 3, "project": "tool-server"},
            {"id": 8, "short_id": "API-8", "title": "old", "culprit": "", "level": "error", "status": "unresolved",
             "first_seen": 10, "last_seen": 1900, "count": 40, "project": "tool-server"},
            {"id": 9, "short_id": "API-9", "title": "fixed", "culprit": "", "level": "error", "status": "resolved",
             "first_seen": 1500, "last_seen": 1600, "count": 1, "project": "tool-server"}]
    out = mc.parse_glitchtip(rows, since=SINCE)
    assert [f.key for f in out] == ["glitchtip:tool-server/API-7", "glitchtip:tool-server/API-8"]
    assert "new" in out[0].title and "recurring" in out[1].title


def test_auto_filed_incidents_in_the_window_become_failures():
    issues = [{"identifier": "EMA-900", "title": "[alert] KubeJobFailed", "url": "https://linear/EMA-900",
               "createdAt": "2026-11-24T02:00:00Z", "state": {"name": "Triage"}}]
    out = mc.parse_linear(issues, since=mc.iso_to_epoch("2026-11-23T12:00:00Z"))
    assert out[0].key == "incident:EMA-900" and out[0].link == "https://linear/EMA-900"


# --- the whole collection ---------------------------------------------------------------------------------------------
def test_an_unreachable_source_is_not_checked_never_nothing_broke():
    def ok(_since):
        return [mc.Failure("ci", "ci:p/s", "t", "e")]

    def down(_since):
        raise mc.SourceUnavailable("Woodpecker answered 502")
    failures, status = mc.collect(SINCE, {"ci": ok, "glitchtip": down})
    assert [f.key for f in failures] == ["ci:p/s"]
    assert status == {"ci": "checked", "glitchtip": "NOT CHECKED: Woodpecker answered 502"}


def test_the_same_cause_from_two_sources_is_one_item():
    f1 = mc.Failure("alerts", "alert:ScheduledJobFailed:weyland/x", "alert", "e1")
    f2 = mc.Failure("alerts", "alert:ScheduledJobFailed:weyland/x", "alert again", "e2")
    failures, _ = mc.collect(SINCE, {"alerts": lambda _s: [f1, f2]})
    assert len(failures) == 1 and "e1" in failures[0].evidence and "e2" in failures[0].evidence


def test_evidence_is_scrubbed_of_secret_shaped_text():
    text = "token=ghp_" + "a" * 36 + " Authorization: Bearer abc.def.ghi password=hunter2"
    clean = mc.scrub(text)
    assert "ghp_" not in clean and "abc.def.ghi" not in clean and "hunter2" not in clean


def test_a_ci_failure_superseded_by_a_later_green_pipeline_is_not_reported():
    # The owner's daytime pushes fail and get fixed; the morning only cares about what is STILL broken.
    assert mc.parse_woodpecker([PIPELINE], {}, since=SINCE, last_green=2500) == []
    assert [f.key for f in mc.parse_woodpecker([PIPELINE], {}, since=SINCE, last_green=1500)] == ["ci:platform/shellcheck"]


def test_a_failed_jobs_log_tail_is_attached_as_scrubbed_evidence():
    item = mc.Failure("alerts", "cronjob:weyland/pr-staleness-check", "t", "ScheduledJobFailed: pr-staleness-check-29923845",
                      extra={"namespace": "weyland", "cronjob": "pr-staleness-check"})
    jobs = "pr-staleness-check-29922405 Failed\npr-staleness-check-29923845 Failed\nother-1 Failed\n"
    logs = {"pr-staleness-check-29923845": "FATAL: GitHub API returned HTTP 404 for edtbl76/Skeets\ntoken=abc123"}
    mc.attach_job_logs([item], list_jobs=lambda ns: jobs, read_log=lambda ns, job: logs[job])
    assert "HTTP 404 for edtbl76/Skeets" in item.evidence and "abc123" not in item.evidence
    assert "pr-staleness-check-29923845" in item.evidence


def test_a_job_whose_log_is_gone_says_so_rather_than_failing_the_source():
    item = mc.Failure("alerts", "cronjob:weyland/x", "t", "e", extra={"namespace": "weyland", "cronjob": "x"})

    def gone(ns, job):
        raise mc.SourceUnavailable("pod gone")
    mc.attach_job_logs([item], list_jobs=lambda ns: "x-29900000 Failed\n", read_log=gone)
    assert "log unavailable" in item.evidence


def test_glitchtip_issues_dagster_filed_about_a_failed_run_merge_into_that_run():
    # Live 2026-11-24: Dagster reports a failed run to GlitchTip itself (STEP_FAILURE and RUN_FAILURE issues titled
    # with the run id), so one cause came back as three items, and two retries were refused as repeats.
    run = "9154c6bc-8ee4-4251-9591-c52245c87146"
    dag = mc.Failure("dagster", "dagster:b243_seed_job", f"Dagster run {run} failed", "step failed",
                     extra={"run_id": run, "job": "b243_seed_job"})
    gt1 = mc.Failure("glitchtip", "glitchtip:weyland-dagster/X-181", f"b243_seed_job - {run} - STEP_FAILURE", "1 event")
    gt2 = mc.Failure("glitchtip", "glitchtip:weyland-dagster/X-182", f"b243_seed_job - {run} - RUN_FAILURE", "2 events")
    other = mc.Failure("glitchtip", "glitchtip:weyland-dagster/X-180", "a real error", "1 event")
    failures, _ = mc.collect(0, {"dagster": lambda _s: [dag], "glitchtip": lambda _s: [gt1, gt2, other]})
    assert [f.key for f in failures] == ["dagster:b243_seed_job", "glitchtip:weyland-dagster/X-180"]
    assert "X-181" in failures[0].evidence and "X-182" in failures[0].evidence


def test_two_failed_runs_of_one_job_are_one_item_that_still_owns_both_runs_reports():
    # Live 2026-11-24 (run 2): two failed runs of b243_seed_job merged under one key and kept only the newer run id,
    # so GlitchTip's reports about the OLDER run were triaged on their own and re-executed it a second time.
    new, old = "0ca5f5b8-4b56-4554-86cb-46d88a580a77", "9154c6bc-8ee4-4251-9591-c52245c87146"
    rows = [{"runId": new, "jobName": "b243_seed_job", "endTime": 3000, "started_by_agent": False, "failures": []},
            {"runId": old, "jobName": "b243_seed_job", "endTime": 2000, "started_by_agent": False, "failures": []}]
    gt = mc.Failure("glitchtip", "glitchtip:weyland-dagster/X-182", f"b243_seed_job - {old} - RUN_FAILURE", "2 events")
    failures, _ = mc.collect(0, {"dagster": lambda _s: mc.parse_dagster(rows), "glitchtip": lambda _s: [gt]})
    assert [f.key for f in failures] == ["dagster:b243_seed_job"]
    assert failures[0].extra["run_id"] == new and failures[0].extra["run_ids"] == [new, old]
    assert "X-182" in failures[0].evidence


# --- first unattended run, 2026-11-25: stale CronJob items -------------------------------------------------------------
def _job(name, owner, failed_at):
    return {"metadata": {"name": name, "namespace": "weyland",
                         "ownerReferences": [{"kind": "CronJob", "name": owner}] if owner else []},
            "status": {"conditions": [{"type": "FailureTarget", "lastTransitionTime": failed_at},
                                      {"type": "Failed", "lastTransitionTime": failed_at}]}}


def _cron(name, last_success):
    return {"metadata": {"name": name, "namespace": "weyland"}, "status": {"lastSuccessfulTime": last_success}}


def _alert(job_name):
    return mc.parse_alerts([{"metric": {"alertname": "KubeJobFailed", "severity": "warning", "namespace": "weyland",
                                        "job_name": job_name}}])[0]


def test_a_hand_started_job_belongs_to_the_cronjob_that_owns_it():
    # Live: code-scan-suite-manual-202611241552 was reported as a CronJob called "code-scan-suite-manual".
    item = _alert("code-scan-suite-manual-202611241552")
    kept = mc.settle_cronjobs([item], {"weyland": [_job("code-scan-suite-manual-202611241552", "code-scan-suite",
                                                        "2026-11-24T21:53:04Z")]},
                              {"weyland": [_cron("code-scan-suite", "2026-11-24T20:00:00Z")]})
    assert [f.key for f in kept] == ["cronjob:weyland/code-scan-suite"]
    assert kept[0].extra["cronjob"] == "code-scan-suite"


def test_a_cronjob_that_succeeded_after_its_failure_is_dropped():
    # Live: the three B259 jobs passed at 04:53Z but their failed Jobs (72 h TTL) kept the alerts firing.
    item = _alert("code-scan-suite-manual-202611241552")
    kept = mc.settle_cronjobs([item], {"weyland": [_job("code-scan-suite-manual-202611241552", "code-scan-suite",
                                                        "2026-11-24T21:53:04Z")]},
                              {"weyland": [_cron("code-scan-suite", "2026-11-25T04:53:12Z")]})
    assert kept == []


def test_a_failure_whose_cronjob_no_longer_exists_is_dropped():
    # Live: the removed b243-seed CronJob's alerts were still inside the 24 h window.
    item = _alert("b243-seed-29924200")
    assert mc.settle_cronjobs([item], {"weyland": []}, {"weyland": []}) == []


def test_other_alerts_pass_through_untouched():
    other = mc.Failure("alerts", "alert:NodeDiskFull:mother", "t", "e", extra={"labels": {}})
    assert mc.settle_cronjobs([other], {}, {}) == [other]


def test_a_canceled_or_done_incident_is_not_collected():
    # Live: EMA-360 had been canceled and still got a comment.
    issues = [{"identifier": "EMA-360", "title": "seed", "url": "u", "createdAt": "2026-11-24T15:05:07Z",
               "state": {"name": "Canceled", "type": "canceled"}},
              {"identifier": "EMA-361", "title": "done", "url": "u", "createdAt": "2026-11-24T15:05:07Z",
               "state": {"name": "Done", "type": "completed"}},
              {"identifier": "EMA-359", "title": "real", "url": "u", "createdAt": "2026-11-24T15:05:07Z",
               "state": {"name": "Todo", "type": "unstarted"}}]
    assert [f.key for f in mc.parse_linear(issues, since=0)] == ["incident:EMA-359"]
