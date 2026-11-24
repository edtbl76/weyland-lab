"""B243: scripts/morning-remediation.py, the entry point the 05:30 timer runs (2026-11-24).

These pin the delivery decisions: which Linear issues get a comment (the incidents the night's items came from),
what the comment and the heartbeat say, and that a delivery is counted only on the service's own success answer
(Slack's literal "ok", Linear's commentCreate.success with an id): a 200 with anything else is a failure.
"""
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
_spec = importlib.util.spec_from_file_location("morning_cli", ROOT / "scripts" / "morning-remediation.py")
cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cli)
mc, mr = cli.mc, cli.mr


def _report(outcomes, status=None):
    return mr.Report("2026-11-24", status or {"ci": "checked"}, outcomes)


def test_only_incident_items_get_a_linear_comment_with_the_outcome():
    inc = mc.Failure("incidents", "incident:EMA-900", "Incident EMA-900: KubeJobFailed", "state Triage",
                     extra={"identifier": "EMA-900"})
    ci = mc.Failure("ci", "ci:p/s", "CI #1 failed", "")
    report = _report([mr.Outcome(inc, mr.NOT_FIXED, "no safe action: needs a person", "unknown", "d"),
                      mr.Outcome(ci, mr.NOT_FIXED, "x")])
    comments = cli.linear_comments(report)
    assert list(comments) == ["EMA-900"]
    assert "not fixed" in comments["EMA-900"] and "needs a person" in comments["EMA-900"]
    assert "B243" in comments["EMA-900"]


def test_the_heartbeat_means_the_run_happened_and_names_unchecked_sources():
    quiet = _report([])
    url = cli.heartbeat_url("https://kuma.example/api/push/tok", quiet)
    assert url.startswith("https://kuma.example/api/push/tok?status=up&msg=") and "quiet" in url
    partial = _report([], {"ci": "checked", "glitchtip": "NOT CHECKED: down"})
    url = cli.heartbeat_url("https://kuma.example/api/push/tok", partial)
    assert "status=up" in url and "NOT+CHECKED" in url and "glitchtip" in url


def test_a_delivery_counts_only_on_the_services_own_success_answer():
    assert cli.slack_ok(200, "ok") and not cli.slack_ok(200, "invalid_payload") and not cli.slack_ok(500, "ok")
    good = {"data": {"commentCreate": {"success": True, "comment": {"id": "c1"}}}}
    assert cli.linear_ok(good) == (True, "c1")
    assert cli.linear_ok({"data": {"commentCreate": {"success": True, "comment": None}}})[0] is False
    assert cli.linear_ok({"errors": [{"message": "FORBIDDEN"}]}) == (False, "FORBIDDEN")


def test_the_summary_line_counts_outcomes():
    ci = mc.Failure("ci", "ci:p/s", "CI #1 failed", "")
    report = _report([mr.Outcome(ci, mr.FIXED, "x"), mr.Outcome(ci, mr.NOT_FIXED, "y")])
    assert cli.summary_line(report) == "2 item(s): 1 fixed by an allowlisted retry, 1 not fixed"
    assert cli.summary_line(_report([])) == "quiet night"
