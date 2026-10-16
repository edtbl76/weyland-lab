"""Tests for sonar_api.py — the canonical way to read SonarQube's API from rogueone (2026-10-02).

Replaces a runbook command that curled from INSIDE the sonarqube pod with `$SONAR_ADMIN_PW`, which the pod does not
carry: it returned 401 and the command had never worked. These pin down the decisions — refuse without a password,
fail closed on any non-200, and summarize a quality gate the way a stopped ship needs to read it.
"""
import io
import json
import os
import sys
import urllib.error
import urllib.parse

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/ on path

import sonar_api as sa


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _serve(monkeypatch, routes, seen=None):
    """Answer urlopen from {api-path: payload}; record each request in `seen`."""
    def urlopen(req, timeout=None):
        path = req.full_url.split("/api/", 1)[1].split("?", 1)[0]
        if seen is not None:
            seen.append(req)
        if path not in routes:
            raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, io.BytesIO(b'{"errors":[]}'))
        return FakeResp(json.dumps(routes[path]).encode())
    monkeypatch.setattr(sa.urllib.request, "urlopen", urlopen)


def test_without_a_password_it_refuses(monkeypatch, capsys):
    monkeypatch.delenv("SONAR_ADMIN_PW", raising=False)
    assert sa.main(["gate"]) == 2
    assert "SONAR_ADMIN_PW" in capsys.readouterr().err


def test_requests_go_to_the_lan_nodeport_with_basic_auth_and_the_params(monkeypatch):
    monkeypatch.setenv("SONAR_ADMIN_PW", "pw")
    seen = []
    _serve(monkeypatch, {"rules/search": {"rules": []}}, seen)
    assert sa.main(["rules/search", "activation=true", "languages=py,java"]) == 0
    req = seen[0]
    assert req.full_url.startswith("http://mother.weyland.lab:30969/api/rules/search?")
    assert "activation=true" in req.full_url and "languages=py%2Cjava" in req.full_url
    assert req.get_header("Authorization").startswith("Basic ")


def test_a_non_200_is_a_failure_not_an_empty_answer(monkeypatch, capsys):
    monkeypatch.setenv("SONAR_ADMIN_PW", "pw")
    _serve(monkeypatch, {})
    assert sa.main(["no/such"]) == 2
    assert "404" in capsys.readouterr().err


def test_a_malformed_param_is_refused(monkeypatch, capsys):
    monkeypatch.setenv("SONAR_ADMIN_PW", "pw")
    assert sa.main(["rules/search", "activation"]) == 2
    assert "key=value" in capsys.readouterr().err


GATE = {"projectStatus": {"status": "ERROR", "conditions": [
    {"status": "OK", "metricKey": "new_coverage", "actualValue": "86.4", "comparator": "LT", "errorThreshold": "80"},
    {"status": "ERROR", "metricKey": "new_violations", "actualValue": "2", "comparator": "GT", "errorThreshold": "0"}]}}
ISSUES = {"total": 1, "issues": [{"severity": "CRITICAL", "rule": "python:S3776", "line": 221,
                                  "component": "weyland-lab:services/x/agent.py",
                                  "message": "Refactor this function to reduce its Cognitive Complexity"}]}
HOTSPOTS = {"paging": {"total": 0}, "hotspots": []}


def test_gate_names_the_failing_condition_and_each_new_issue(monkeypatch, capsys):
    monkeypatch.setenv("SONAR_ADMIN_PW", "pw")
    _serve(monkeypatch, {"qualitygates/project_status": GATE, "issues/search": ISSUES, "hotspots/search": HOTSPOTS})
    assert sa.main(["gate"]) == 1                       # a failing gate is exit 1 — readable, and distinct from 2
    out = capsys.readouterr().out
    assert "gate weyland-lab: ERROR" in out
    assert "ERROR new_violations 2 (GT 0)" in out
    assert "python:S3776 services/x/agent.py:221" in out
    assert "hotspots to review: 0" in out


def test_a_passing_gate_is_exit_0(monkeypatch):
    monkeypatch.setenv("SONAR_ADMIN_PW", "pw")
    ok = {"projectStatus": {"status": "OK", "conditions": []}}
    _serve(monkeypatch, {"qualitygates/project_status": ok, "issues/search": {"total": 0, "issues": []},
                         "hotspots/search": HOTSPOTS})
    assert sa.main(["gate"]) == 0


# review-safe (2026-10-03): mark a file's new-code hotspots REVIEWED/SAFE with a stated reason — the command the
# runbook lacked when moving 7 in-cluster http:// URLs into a new file re-raised them as new hotspots.
CFG = "nodes/x/config.py"
TO_REVIEW = {"paging": {"total": 3}, "hotspots": [
    {"key": "AAA", "line": 13, "component": f"weyland-lab:{CFG}", "vulnerabilityProbability": "LOW", "message": "http"},
    {"key": "BBB", "line": 14, "component": f"weyland-lab:{CFG}", "vulnerabilityProbability": "LOW", "message": "http"},
    {"key": "CCC", "line": 9, "component": "weyland-lab:other.py", "vulnerabilityProbability": "LOW", "message": "x"}]}
REASON = "in-cluster ClusterIP traffic; the upstream services serve plain HTTP"


def test_review_safe_reviews_only_that_files_hotspots_with_the_reason(monkeypatch, capsys):
    monkeypatch.setenv("SONAR_ADMIN_PW", "pw")
    seen = []
    _serve(monkeypatch, {"hotspots/search": TO_REVIEW, "hotspots/change_status": {}}, seen)
    assert sa.main(["review-safe", CFG, REASON]) == 0
    posts = [r for r in seen if r.get_method() == "POST"]
    assert len(posts) == 2                                  # CCC is in another file — untouched
    body = posts[0].data.decode()
    assert "hotspot=AAA" in body and "status=REVIEWED" in body and "resolution=SAFE" in body
    assert "ClusterIP" in urllib.parse.unquote_plus(body)
    assert f"reviewed SAFE {CFG}:14 BBB" in capsys.readouterr().out


def test_review_safe_with_nothing_to_review_fails_closed(monkeypatch, capsys):
    monkeypatch.setenv("SONAR_ADMIN_PW", "pw")
    _serve(monkeypatch, {"hotspots/search": TO_REVIEW})
    assert sa.main(["review-safe", "no/such/file.py", REASON]) == 2   # a typo'd path must not read as "done"
    assert "no new-code hotspots to review in no/such/file.py" in capsys.readouterr().err


def test_review_safe_refuses_without_a_reason(monkeypatch, capsys):
    monkeypatch.setenv("SONAR_ADMIN_PW", "pw")
    assert sa.main(["review-safe", CFG]) == 2
    assert "a reason is required" in capsys.readouterr().err


# precheck (2026-10-13): scan changed files in a throwaway project BEFORE handoff — the CI sonar-gate blocks the build
# and the nightly ship, and nothing local ran Sonar (B190's push failed CI #279 on 18 new-code issues). Shapes OBSERVED
# 2026-10-13: user_tokens/generate → {"token": …}; measures/component → {"component": {"measures": [{"metric": "files",
# "value": "374"}]}}. A scratch project's first analysis has no new-code period, so its gate PASSED with a CRITICAL
# issue open — the verdict is the findings, never the scratch gate.

REAL_CHANGED_LINES = sa._changed_lines   # the autouse fixture below replaces it; the git test needs the real one


@pytest.fixture(autouse=True)
def _no_changed_lines(monkeypatch):
    """Default: the change touched none of the lines Sonar reports, so "already open" stays already open. The tests
    for the changed-line rule below replace this."""
    monkeypatch.setattr(sa, "_changed_lines", lambda paths: {})


class Scanner:
    """Stands in for the docker sonar-scanner run; records what it was asked to scan."""

    def __init__(self, rc=0, output="INFO  EXECUTION SUCCESS"):
        self.rc, self.output, self.calls = rc, output, []

    def __call__(self, src, key, token):
        self.calls.append({"files": sorted(str(p.relative_to(src)) for p in __import__("pathlib").Path(src).rglob("*")
                                           if p.is_file()), "key": key, "token": token})
        return self.rc, self.output


def _precheck_routes(issues=None, hotspots=None, files="2"):
    return {"user_tokens/generate": {"token": "squ_secret"}, "user_tokens/revoke": {}, "projects/delete": {},
            "ce/component": {"queue": [], "current": {"status": "SUCCESS"}},
            "measures/component": {"component": {"measures": [{"metric": "files", "value": files}]}},
            "issues/search": issues or {"total": 0, "issues": []},
            "hotspots/search": hotspots or {"paging": {"total": 0}, "hotspots": []}}


def _src(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text("x = 1\n")
    (tmp_path / "b.py").write_text("y = 2\n")
    return ["pkg/a.py", "b.py"]


def _posted(seen, path):
    return [urllib.parse.parse_qs(r.data.decode()) for r in seen
            if r.get_method() == "POST" and r.full_url.endswith(f"/api/{path}")]


def test_precheck_clean_scan_is_exit_0_and_always_cleans_up(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SONAR_ADMIN_PW", "pw")
    files, seen, scan = _src(tmp_path, monkeypatch), [], Scanner()
    _serve(monkeypatch, _precheck_routes(), seen)
    monkeypatch.setattr(sa, "_run_scanner", scan)
    assert sa.main(["precheck", *files]) == 0
    assert scan.calls[0]["files"] == ["b.py", "pkg/a.py"]          # repo-relative paths kept, so findings read well
    key = scan.calls[0]["key"]
    assert key.startswith("weyland-lab-precheck-") and key != sa.PROJECT   # never the real project
    assert _posted(seen, "projects/delete")[0]["project"] == [key]
    assert _posted(seen, "user_tokens/revoke")[0]["name"] == [key]
    out = capsys.readouterr()
    assert "precheck: clean (2 files scanned, 0 issues, 0 hotspots)" in out.out
    assert "squ_secret" not in out.out + out.err                   # the minted token is never printed


def test_precheck_findings_are_exit_1_and_named(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SONAR_ADMIN_PW", "pw")
    files, seen = _src(tmp_path, monkeypatch), []
    issues = {"total": 1, "issues": [{"severity": "CRITICAL", "rule": "python:S3776", "line": 97,
                                      "component": "weyland-lab-precheck-1:pkg/a.py", "message": "Cognitive Complexity"}]}
    hotspots = {"paging": {"total": 1}, "hotspots": [{"vulnerabilityProbability": "LOW", "line": 3,
                                                      "component": "weyland-lab-precheck-1:b.py", "message": "http"}]}
    _serve(monkeypatch, _precheck_routes(issues, hotspots), seen)
    real = sa.get                              # weyland-lab has nothing open or reviewed for these files
    monkeypatch.setattr(sa, "get", lambda p, q: {"paging": {"total": 0}, "hotspots": []}
                        if p == "hotspots/search" and q.get("projectKey") == sa.PROJECT
                        else ({"total": 0, "issues": []}
                              if p == "issues/search" and q.get("componentKeys", "").startswith(sa.PROJECT + ":")
                              else real(p, q)))
    monkeypatch.setattr(sa, "_run_scanner", Scanner())
    assert sa.main(["precheck", *files]) == 1
    out = capsys.readouterr().out
    assert "CRITICAL python:S3776 pkg/a.py:97" in out and "LOW b.py:3" in out
    assert _posted(seen, "projects/delete") and _posted(seen, "user_tokens/revoke")


def test_precheck_does_not_count_a_hotspot_already_reviewed_safe_on_the_real_project(tmp_path, monkeypatch, capsys):
    # Observed 2026-10-13: sonar_api.py's own http:// hotspot (reviewed SAFE on weyland-lab, line 26) came back on the
    # scratch project at line 33 — lines move, so the match is file + rule + message.
    monkeypatch.setenv("SONAR_ADMIN_PW", "pw")
    files = _src(tmp_path, monkeypatch)
    http = "Using http protocol is insecure. Use https instead"
    scratch = {"paging": {"total": 2}, "hotspots": [
        {"vulnerabilityProbability": "LOW", "line": 33, "ruleKey": "python:S5332", "message": http,
         "component": "weyland-lab-precheck-1:b.py"},
        {"vulnerabilityProbability": "LOW", "line": 4, "ruleKey": "python:S5332", "message": http,
         "component": "weyland-lab-precheck-1:pkg/a.py"}]}
    reviewed = {"paging": {"total": 1}, "hotspots": [
        {"line": 26, "ruleKey": "python:S5332", "message": http, "component": "weyland-lab:b.py"}]}
    routes = _precheck_routes()
    _serve(monkeypatch, routes)
    real = sa.get
    monkeypatch.setattr(sa, "get", lambda p, q: (reviewed if q.get("projectKey") == sa.PROJECT else scratch)
                        if p == "hotspots/search" else real(p, q))
    monkeypatch.setattr(sa, "_run_scanner", Scanner())
    assert sa.main(["precheck", *files]) == 1                      # pkg/a.py's is new
    out = capsys.readouterr().out
    assert "already reviewed SAFE on weyland-lab: b.py:33" in out
    assert "precheck: FINDINGS (2 files scanned, 0 issues, 1 hotspots, 1 already reviewed)" in out


def test_precheck_scanner_failure_is_exit_2_not_clean(tmp_path, monkeypatch, capsys):
    # Observed 2026-10-12: without host networking the scanner could not resolve mother.weyland.lab, exited 1, and a
    # naive read of issues/search would have said "0 issues".
    monkeypatch.setenv("SONAR_ADMIN_PW", "pw")
    files, seen = _src(tmp_path, monkeypatch), []
    _serve(monkeypatch, _precheck_routes(), seen)
    monkeypatch.setattr(sa, "_run_scanner", Scanner(rc=1, output="ERROR Failed to query server version"))
    assert sa.main(["precheck", *files]) == 2
    assert "Failed to query server version" in capsys.readouterr().err
    assert _posted(seen, "user_tokens/revoke")                      # cleanup runs on the failure path too


def test_precheck_that_scanned_no_files_is_exit_2(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SONAR_ADMIN_PW", "pw")
    files = _src(tmp_path, monkeypatch)
    _serve(monkeypatch, _precheck_routes(files="0"))
    monkeypatch.setattr(sa, "_run_scanner", Scanner())
    assert sa.main(["precheck", *files]) == 2                      # analysed nothing ≠ found nothing
    assert "scanned 0 files" in capsys.readouterr().err


def test_precheck_waits_for_sonar_to_process_the_report(tmp_path, monkeypatch, capsys):
    # Observed 2026-10-13 (first live run): the scanner returns once the report is UPLOADED; read at once, the project
    # had 0 files. The precheck waits on ce/component (shape observed: {"queue": [...], "current": {"status": …}}).
    monkeypatch.setenv("SONAR_ADMIN_PW", "pw")
    files, seen = _src(tmp_path, monkeypatch), []
    states = iter([{"queue": [{"status": "PENDING"}]}, {"queue": [{"status": "IN_PROGRESS"}]},
                   {"queue": [], "current": {"status": "SUCCESS"}}])
    routes = _precheck_routes()
    _serve(monkeypatch, routes, seen)
    real = sa.get
    monkeypatch.setattr(sa, "get", lambda p, q: next(states) if p == "ce/component" else real(p, q))
    monkeypatch.setattr(sa.time, "sleep", lambda s: None)
    monkeypatch.setattr(sa, "_run_scanner", Scanner())
    assert sa.main(["precheck", *files]) == 0
    assert next(states, "drained") == "drained"                    # it polled until the task finished


def test_precheck_failed_analysis_is_exit_2(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SONAR_ADMIN_PW", "pw")
    files = _src(tmp_path, monkeypatch)
    routes = _precheck_routes()
    routes["ce/component"] = {"queue": [], "current": {"status": "FAILED", "errorMessage": "boom"}}
    _serve(monkeypatch, routes)
    monkeypatch.setattr(sa, "_run_scanner", Scanner())
    assert sa.main(["precheck", *files]) == 2
    assert "FAILED" in capsys.readouterr().err


def test_precheck_refuses_missing_files_before_touching_sonar(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SONAR_ADMIN_PW", "pw")
    _src(tmp_path, monkeypatch)
    seen = []
    _serve(monkeypatch, _precheck_routes(), seen)
    assert sa.main(["precheck", "b.py", "no/such.py"]) == 2
    assert "no/such.py" in capsys.readouterr().err and seen == []  # no token minted for a typo
    assert sa.main(["precheck"]) == 2


def test_precheck_reports_a_failed_token_revoke(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SONAR_ADMIN_PW", "pw")
    files = _src(tmp_path, monkeypatch)
    routes = _precheck_routes()
    del routes["user_tokens/revoke"]                               # 404 → a live admin token would be left behind
    _serve(monkeypatch, routes)
    monkeypatch.setattr(sa, "_run_scanner", Scanner())
    assert sa.main(["precheck", *files]) == 2
    assert "revoke" in capsys.readouterr().err


def test_precheck_with_only_files_sonar_does_not_analyse_is_exit_0_without_scanning(tmp_path, monkeypatch, capsys):
    # Observed 2026-10-13: a shell + Markdown + bats change scanned 0 files and exited 2, so the AGENTS.md rule
    # ("must print precheck: clean") could never pass for it. Only KNOWN non-analysed types skip; nothing is minted.
    monkeypatch.setenv("SONAR_ADMIN_PW", "pw")
    monkeypatch.chdir(tmp_path)
    for name in ("a.sh", "b.md", "c.bats", "d.tsv"):
        (tmp_path / name).write_text("x\n")
    seen = []
    _serve(monkeypatch, _precheck_routes(), seen)
    assert sa.main(["precheck", "a.sh", "b.md", "c.bats", "d.tsv"]) == 0
    assert seen == []
    assert "precheck: nothing for Sonar to analyse (4 files: .bats .md .sh .tsv)" in capsys.readouterr().out


def test_precheck_scans_when_any_file_might_be_analysed(tmp_path, monkeypatch):
    monkeypatch.setenv("SONAR_ADMIN_PW", "pw")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.md").write_text("x\n")
    (tmp_path / "app.js").write_text("let x = 1\n")                # analysed types are always scanned
    scan = Scanner()
    _serve(monkeypatch, _precheck_routes())
    monkeypatch.setattr(sa, "_run_scanner", scan)
    assert sa.main(["precheck", "a.md", "app.js"]) == 0
    assert scan.calls[0]["files"] == ["a.md", "app.js"]


def test_precheck_does_not_count_an_issue_already_open_on_the_real_project(tmp_path, monkeypatch, capsys):
    # Observed 2026-10-13 (B207): a 3-line change to weyland-tool-server/main.py pre-checked as 19 issues — exactly the
    # 19 already open on weyland-lab for that file (a scratch project has no new-code period, so every line is "new").
    # The rule ("must print clean") could never pass for an edit to a big file. Matched on file + rule + message.
    monkeypatch.setenv("SONAR_ADMIN_PW", "pw")
    files = _src(tmp_path, monkeypatch)
    scratch = {"total": 2, "issues": [
        {"severity": "MAJOR", "rule": "python:S8415", "line": 80, "message": "Document this HTTPException",
         "component": "weyland-lab-precheck-1:b.py"},
        {"severity": "MAJOR", "rule": "python:S8415", "line": 12, "message": "Document this HTTPException",
         "component": "weyland-lab-precheck-1:pkg/a.py"}]}
    already = {"total": 1, "issues": [
        {"severity": "MAJOR", "rule": "python:S8415", "line": 77, "message": "Document this HTTPException",
         "component": "weyland-lab:b.py"}]}
    _serve(monkeypatch, _precheck_routes())
    real = sa.get
    def fake_get(path, q):
        if path == "issues/search":
            return already if q.get("componentKeys", "").startswith(sa.PROJECT + ":") else scratch
        if path == "hotspots/search":
            return {"paging": {"total": 0}, "hotspots": []}
        return real(path, q)
    monkeypatch.setattr(sa, "get", fake_get)
    monkeypatch.setattr(sa, "_run_scanner", Scanner())
    assert sa.main(["precheck", *files]) == 1                      # pkg/a.py's is new
    out = capsys.readouterr().out
    assert "already open on weyland-lab: b.py:80" in out
    assert "precheck: FINDINGS (2 files scanned, 1 issues, 0 hotspots, 1 already open)" in out


def test_precheck_with_only_already_open_issues_is_clean(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SONAR_ADMIN_PW", "pw")
    files = _src(tmp_path, monkeypatch)
    issue = {"severity": "MINOR", "rule": "python:S1313", "message": "IP address", "line": 5}
    _serve(monkeypatch, _precheck_routes())
    real = sa.get
    monkeypatch.setattr(sa, "get", lambda path, q: (
        {"total": 1, "issues": [{**issue, "component": f"{sa.PROJECT}:b.py"}]}
        if q.get("componentKeys", "").startswith(sa.PROJECT + ":")
        else {"total": 1, "issues": [{**issue, "component": "weyland-lab-precheck-9:b.py"}]})
        if path == "issues/search" else
        ({"paging": {"total": 0}, "hotspots": []} if path == "hotspots/search" else real(path, q)))
    monkeypatch.setattr(sa, "_run_scanner", Scanner())
    assert sa.main(["precheck", *files]) == 0
    assert "precheck: clean (2 files scanned, 0 issues, 0 hotspots, 1 already open)" in capsys.readouterr().out


def test_precheck_does_not_count_a_hotspot_already_open_to_review_on_the_real_project(tmp_path, monkeypatch, capsys):
    # Observed 2026-10-13 (B207): main.py's 11 http:// hotspots are TO_REVIEW (not reviewed SAFE) on weyland-lab —
    # old code, not this change's. Reviewed SAFE → "already reviewed"; still TO_REVIEW → "already open".
    monkeypatch.setenv("SONAR_ADMIN_PW", "pw")
    files = _src(tmp_path, monkeypatch)
    http = "Using http protocol is insecure. Use https instead"
    scratch = {"paging": {"total": 1}, "hotspots": [
        {"vulnerabilityProbability": "LOW", "line": 81, "ruleKey": "python:S5332", "message": http,
         "component": "weyland-lab-precheck-1:b.py"}]}
    to_review = {"paging": {"total": 1}, "hotspots": [
        {"line": 79, "ruleKey": "python:S5332", "message": http, "component": "weyland-lab:b.py", "status": "TO_REVIEW"}]}
    _serve(monkeypatch, _precheck_routes())
    real = sa.get

    def fake_get(path, q):
        if path == "hotspots/search":
            if q.get("projectKey") != sa.PROJECT:
                return scratch
            return to_review if q.get("status") == "TO_REVIEW" else {"paging": {"total": 0}, "hotspots": []}
        if path == "issues/search" and q.get("componentKeys", "").startswith(sa.PROJECT + ":"):
            return {"total": 0, "issues": []}
        return real(path, q)
    monkeypatch.setattr(sa, "get", fake_get)
    monkeypatch.setattr(sa, "_run_scanner", Scanner())
    assert sa.main(["precheck", *files]) == 0
    out = capsys.readouterr().out
    assert "already open on weyland-lab: b.py:81" in out
    assert "precheck: clean (2 files scanned, 0 issues, 0 hotspots, 1 already open)" in out


# The pre-check judges a change by the CI gate's rules, so it must scan what the gate scans. sonar-project.properties
# excludes **/*.yaml, Dockerfiles, Terraform… (observed 2026-10-13: a k8s manifest change pre-checked as 1 issue + 6
# hotspots that the real project never sees).
def _props(tmp_path, monkeypatch, exclusions):
    p = tmp_path / "sonar-project.properties"
    p.write_text(f"sonar.projectKey=weyland-lab\nsonar.exclusions={exclusions}\n")
    monkeypatch.setenv("SONAR_PROJECT_PROPERTIES", str(p))


def test_precheck_drops_files_the_project_excludes(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SONAR_ADMIN_PW", "pw")
    files = _src(tmp_path, monkeypatch)
    (tmp_path / "k8s").mkdir()
    (tmp_path / "k8s" / "app.yaml").write_text("kind: x\n")
    (tmp_path / "Dockerfile").write_text("FROM x\n")
    _props(tmp_path, monkeypatch, "**/node_modules/**,**/*.yaml,**/Dockerfile")
    scan = Scanner()
    _serve(monkeypatch, _precheck_routes())
    monkeypatch.setattr(sa, "_run_scanner", scan)
    assert sa.main(["precheck", *files, "k8s/app.yaml", "Dockerfile"]) == 0
    assert scan.calls[0]["files"] == ["b.py", "pkg/a.py"]
    assert "2 excluded by sonar-project.properties: Dockerfile k8s/app.yaml" in capsys.readouterr().out


def test_precheck_with_only_excluded_files_has_nothing_to_analyse(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SONAR_ADMIN_PW", "pw")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "x.yaml").write_text("a: 1\n")
    _props(tmp_path, monkeypatch, "**/*.yaml")
    seen = []
    _serve(monkeypatch, _precheck_routes(), seen)
    assert sa.main(["precheck", "x.yaml"]) == 0
    assert seen == []
    assert "precheck: nothing for Sonar to analyse" in capsys.readouterr().out


def test_ant_patterns_match_like_sonar():
    m = sa._excluded
    assert m("a/b/node_modules/c/d.js", ["**/node_modules/**"]) and m("node_modules/x.js", ["**/node_modules/**"])
    assert m("deep/k.yaml", ["**/*.yaml"]) and m("k.yaml", ["**/*.yaml"])
    assert m("site-techdocs/x/y.html", ["site-techdocs/**"]) and not m("docs/site-techdocs.md", ["site-techdocs/**"])
    assert not m("app.py", ["**/*.yaml", "**/Dockerfile"]) and m("svc/Dockerfile.dev", ["**/Dockerfile.*"])


# 2026-10-16 (CI #387, #388): an issue already open on weyland-lab, on a line the change EDITED, is new code to the CI
# gate. The precheck listed `"*/openclaw/*"` (S1192) as "already open" and printed clean; CI failed on it twice, because
# editing the line that carries a duplicated literal makes that line new code.
def _already_open_routes(monkeypatch, line=80):
    scratch = {"total": 1, "issues": [{"severity": "CRITICAL", "rule": "python:S1192", "line": line,
                                       "message": "Define a constant", "component": "weyland-lab-precheck-1:b.py"}]}
    already = {"total": 1, "issues": [{"severity": "CRITICAL", "rule": "python:S1192", "line": 77,
                                       "message": "Define a constant", "component": "weyland-lab:b.py"}]}
    _serve(monkeypatch, _precheck_routes())
    real = sa.get

    def fake_get(path, q):
        if path == "issues/search":
            return already if q.get("componentKeys", "").startswith(sa.PROJECT + ":") else scratch
        if path == "hotspots/search":
            return {"paging": {"total": 0}, "hotspots": []}
        return real(path, q)
    monkeypatch.setattr(sa, "get", fake_get)
    monkeypatch.setattr(sa, "_run_scanner", Scanner())


def test_an_already_open_issue_on_a_changed_line_counts_as_new(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SONAR_ADMIN_PW", "pw")
    files = _src(tmp_path, monkeypatch)
    _already_open_routes(monkeypatch, line=80)
    monkeypatch.setattr(sa, "_changed_lines", lambda paths: {"b.py": {79, 80, 81}})
    assert sa.main(["precheck", *files]) == 1
    out = capsys.readouterr().out
    assert "CRITICAL python:S1192 b.py:80" in out and "on a line this change edits" in out
    assert "precheck: FINDINGS (2 files scanned, 1 issues, 0 hotspots)" in out


def test_an_already_open_issue_on_an_untouched_line_stays_already_open(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SONAR_ADMIN_PW", "pw")
    files = _src(tmp_path, monkeypatch)
    _already_open_routes(monkeypatch, line=80)
    monkeypatch.setattr(sa, "_changed_lines", lambda paths: {"b.py": {3, 4}})
    assert sa.main(["precheck", *files]) == 0
    assert "precheck: clean (2 files scanned, 0 issues, 0 hotspots, 1 already open)" in capsys.readouterr().out


def test_unreadable_changed_lines_is_exit_2_not_clean(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SONAR_ADMIN_PW", "pw")
    files = _src(tmp_path, monkeypatch)
    _already_open_routes(monkeypatch, line=80)

    def boom(paths):
        raise sa.CannotRead("git diff origin/main: not a git repository")
    monkeypatch.setattr(sa, "_changed_lines", boom)
    assert sa.main(["precheck", *files]) == 2
    assert "cannot tell which lines this change edits" in capsys.readouterr().err


def test_changed_lines_without_git_is_cannot_read(monkeypatch):
    def no_git(*a, **k):
        raise FileNotFoundError("git")
    monkeypatch.setattr(sa.subprocess, "run", no_git)
    with pytest.raises(sa.CannotRead, match="git is not installed"):
        REAL_CHANGED_LINES(["f.py"])


def test_changed_lines_reads_the_new_side_of_a_real_git_diff(tmp_path, monkeypatch):
    import shutil
    import subprocess
    if not shutil.which("git"):
        pytest.skip("git is not in this image (CI's python:3.12-slim); runs wherever git exists")
    monkeypatch.chdir(tmp_path)
    run = lambda *a: subprocess.run(["git", *a], check=True, capture_output=True)
    run("init", "-q"); run("config", "user.email", "t@t"); run("config", "user.name", "t")
    (tmp_path / "f.py").write_text("a\nb\nc\nd\n")
    run("add", "f.py"); run("commit", "-qm", "base")
    run("update-ref", "refs/remotes/origin/main", "HEAD")
    (tmp_path / "f.py").write_text("a\nB\nc\nd\ne\n")             # line 2 changed, line 5 added
    assert REAL_CHANGED_LINES(["f.py"]) == {"f.py": {2, 5}}
