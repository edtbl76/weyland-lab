"""Tests for the operator's act executor (B66 Part 3) — the FIRE half of the confirm rail.

This is a safety boundary: the LLM can only PROPOSE; `fire` is the only path that actually launches, and it must be
fail-closed — an unknown tool or a job_name off the allowlist is refused BEFORE any HTTP call. A regression here would
let the operator launch an unintended job on a user "yes". Pure decision logic + HTTP-result shaping (httpx stubbed).
"""
import httpx
import pytest

import act


# ── describe: the confirm-prompt line ────────────────────────────────────────────────────────────────
def test_describe_with_summary_and_job():
    line = act.describe({"tool": "pipeline_trigger", "job_name": "weyland_eval_job", "summary": "run the evals"})
    assert line == "run the evals — will run `pipeline_trigger (job: weyland_eval_job)`"


def test_describe_without_summary_or_job():
    assert act.describe({"tool": "evals_run"}) == "will run `evals_run`"


# ── fire: fail-closed rails (return BEFORE any HTTP call) ─────────────────────────────────────────────
def test_fire_refuses_unknown_tool():
    assert act.fire({"tool": "rm_rf_prod"}, actor=None) == "⛔ Unknown action `rm_rf_prod` — refused."


def test_fire_refuses_job_off_the_allowlist():
    out = act.fire({"tool": "pipeline_trigger", "job_name": "delete_everything"}, actor=None)
    assert out == "⛔ Job `delete_everything` is not on the allowlist — refused."


def test_fire_accepts_allowlisted_job_and_reports_the_run(monkeypatch):
    sent = {}

    class _Resp:
        status_code = 200
        def json(self): return {"job_name": "weyland_eval_job", "run_id": "run-42"}

    def _post(url, json=None, headers=None, timeout=None):
        sent["url"] = url; sent["json"] = json; sent["headers"] = headers
        return _Resp()

    monkeypatch.setattr(act.httpx, "post", _post)
    out = act.fire({"tool": "pipeline_trigger", "job_name": "weyland_eval_job", "summary": "s"}, actor="ed")
    assert "✅ Launched `weyland_eval_job`" in out and "run-42" in out
    assert sent["json"] == {"job_name": "weyland_eval_job"}          # the allowlisted job is what got sent
    assert sent["url"].endswith("/pipeline/trigger")


def test_fire_surfaces_a_rejection_status(monkeypatch):
    class _Resp:
        status_code = 403
        text = "guard blocked"
        def json(self): return {}
    monkeypatch.setattr(act.httpx, "post", lambda *a, **k: _Resp())
    out = act.fire({"tool": "evals_run"}, actor="ed")
    assert out.startswith("⚠️ Action rejected (403)") and "guard blocked" in out


def test_fire_fails_open_message_on_transport_error(monkeypatch):
    def _boom(*a, **k): raise httpx.ConnectError("no route")
    monkeypatch.setattr(act.httpx, "post", _boom)
    out = act.fire({"tool": "evals_run"}, actor="ed")
    assert "failed to reach" in out


# ── _token: no secret → legacy path (None) ───────────────────────────────────────────────────────────
def test_token_is_none_without_a_client_secret(monkeypatch):
    monkeypatch.setattr(act, "CLIENT_SECRET", "")
    assert act._token() is None
