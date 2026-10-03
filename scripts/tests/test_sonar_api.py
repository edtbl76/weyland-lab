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
