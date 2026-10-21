"""Tests for the incident-sweep triage logic (B45, ENRICH-ONLY).

The sweep reads firing alerts from Prometheus and must (a) skip alerts that fire BY DESIGN so the digest stays
real-signal-only, (b) fingerprint each firing episode stably so it notifies once, and (c) build an enrich-only
investigation prompt that never asks the agent to act. Those decisions are the pure functions tested here; the
async Prometheus/agent/Telegram round-trips (stubbed siblings) are validated live.
"""
import asyncio
import json
import os
import subprocess
import sys

import pytest

import incidents


def test_is_incident_true_for_a_real_firing_alert():
    assert incidents._is_incident({"severity": "warning", "alertname": "TargetDown"})


def test_is_incident_false_for_severity_none():
    # Watchdog / InfoInhibitor dead-man's-switches carry severity=none and fire forever.
    assert not incidents._is_incident({"severity": "none", "alertname": "Whatever"})


def test_is_incident_false_for_by_design_alertnames():
    # default INCIDENT_SKIP_ALERTS includes Watchdog / InfoInhibitor / LiteLLMEgressEnabled
    for name in ("Watchdog", "InfoInhibitor", "LiteLLMEgressEnabled"):
        assert not incidents._is_incident({"severity": "warning", "alertname": name}), name


def test_fingerprint_is_stable_for_the_same_alert():
    labels = {"alertname": "TargetDown", "instance": "10.0.0.1", "pod": "p", "job": "j", "namespace": "weyland"}
    assert incidents._fingerprint(labels) == incidents._fingerprint(dict(labels))


def test_fingerprint_distinguishes_different_identities():
    a = {"alertname": "TargetDown", "pod": "pod-a"}
    b = {"alertname": "TargetDown", "pod": "pod-b"}
    assert incidents._fingerprint(a) != incidents._fingerprint(b)


def test_fingerprint_ignores_non_identity_labels():
    base = {"alertname": "X", "instance": "i", "pod": "p", "job": "j", "namespace": "n"}
    noisy = dict(base, severity="critical", extra="whatever")
    assert incidents._fingerprint(base) == incidents._fingerprint(noisy)


def test_who_prefers_instance_then_pod_then_job_then_placeholder():
    assert incidents._who({"instance": "i", "pod": "p", "job": "j"}) == "i"
    assert incidents._who({"pod": "p", "job": "j"}) == "p"
    assert incidents._who({"job": "j"}) == "j"
    assert incidents._who({}) == "?"


def test_investigation_prompt_is_enrich_only_and_names_the_alert():
    prompt = incidents._investigation_prompt({"alertname": "PodCrashLooping", "severity": "critical", "pod": "api-1"})
    assert "PodCrashLooping" in prompt and "api-1" in prompt
    assert "Do NOT" in prompt          # ENRICH-ONLY — never asks the agent to act


# --- 2026-10-02: a sweep never pays — when the local brain is busy it defers, it does not fail over to Haiku ---------

A = {"alertname": "TargetDown", "severity": "warning", "pod": "pod-a"}
B = {"alertname": "TargetDown", "severity": "warning", "pod": "pod-b"}


@pytest.fixture
def sweep(monkeypatch):
    """sweep_once with Prometheus, the agent, Telegram and the incident store replaced by recorders."""
    rec = {"runs": [], "sent": [], "recorded": [], "cleared": None, "agent": None}

    async def firing(_client):
        return [A, B]

    async def run(message, history, **kw):
        rec["runs"].append(kw)
        if rec["agent"] is not None:
            raise rec["agent"]
        return ("enriched", None)

    async def send(_client, chat, text):
        rec["sent"].append((chat, text))

    monkeypatch.setattr(incidents, "_firing", firing)
    monkeypatch.setattr(incidents, "_CHAT_ID", "42")
    monkeypatch.setattr(incidents.agent, "run", run)
    monkeypatch.setattr(incidents.telegram, "send_message", send, raising=False)
    monkeypatch.setattr(incidents.session, "incidents_recorded", lambda: set(), raising=False)
    monkeypatch.setattr(incidents.session, "incident_record", lambda fp, _l: rec["recorded"].append(fp), raising=False)
    monkeypatch.setattr(incidents.session, "incidents_clear_resolved",
                        lambda fps: rec.__setitem__("cleared", fps), raising=False)
    return rec


def test_a_sweep_asks_the_agent_without_the_paid_fallback(sweep):
    assert asyncio.run(incidents.sweep_once(None)) == "ok"
    assert sweep["runs"] and all(kw.get("allow_fallback") is False for kw in sweep["runs"])
    assert len(sweep["sent"]) == 2 and len(sweep["recorded"]) == 2


def test_local_unavailable_defers_the_sweep_sends_nothing_and_records_nothing(sweep):
    sweep["agent"] = incidents.agent.LocalUnavailable("local brain unavailable")
    assert asyncio.run(incidents.sweep_once(None)) == "deferred"
    assert sweep["sent"] == [] and sweep["recorded"] == []    # unrecorded -> the next sweep retries them
    assert len(sweep["runs"]) == 1                            # stops at the first: no point asking again this sweep
    assert sweep["cleared"] is not None                       # still forgets alerts that resolved meanwhile


def test_any_other_enrichment_error_still_notifies(sweep):
    sweep["agent"] = RuntimeError("fleet down")
    assert asyncio.run(incidents.sweep_once(None)) == "ok"
    assert len(sweep["sent"]) == 2 and "enrichment failed: fleet down" in sweep["sent"][0][1]


def test_an_empty_local_reply_notifies_with_the_reason_it_does_not_defer(sweep):
    # 2026-10-03: qwen2.5:7b replies empty after a fleet tool call EVERY time — it is bad output, not a busy engine.
    # Deferring would retry it forever and the incident would never be posted; post it with the reason instead.
    sweep["agent"] = incidents.agent.EmptyReply("qwen2.5:7b returned an empty reply")
    assert asyncio.run(incidents.sweep_once(None)) == "ok"
    assert len(sweep["sent"]) == 2 and len(sweep["recorded"]) == 2
    assert "enrichment failed: qwen2.5:7b returned an empty reply" in sweep["sent"][0][1]


def test_the_sweep_can_be_switched_back_to_paid_haiku(sweep, monkeypatch):
    # INCIDENT_SWEEP_ALLOW_PAID=true restores the Haiku failover (and the Realm) for sweeps — the owner's switch.
    monkeypatch.setattr(incidents, "SWEEP_ALLOW_PAID", True)
    asyncio.run(incidents.sweep_once(None))
    assert sweep["runs"] and all(kw.get("allow_fallback") is True for kw in sweep["runs"])


def test_the_paid_switch_defaults_off():
    assert incidents.SWEEP_ALLOW_PAID is False


# --- B174: the decision-model shadow rides the sweep, after the agent, and never changes it -----------------------------

@pytest.fixture
def shadow(sweep, monkeypatch):
    """The sweep with the decision-model shadow switched on; records every shadow call."""
    calls = []

    async def run(message, history, trace=None, **kw):
        sweep["runs"].append(kw)
        if sweep["agent"] is not None:
            raise sweep["agent"]
        if trace is not None:
            trace["first_tool"] = "k8s_pods_list"
        return ("enriched", None)

    async def fake_shadow(client, rules, request, tools, actual, alert):
        calls.append({"request": request, "tools": tools, "actual": actual, "alert": alert, "rules": rules})
        return {"choice": "k8s_pods_log", "outcome": "disagree"}

    monkeypatch.setattr(incidents.agent, "run", run)
    monkeypatch.setattr(incidents.agent, "sweep_tools", lambda: [("k8s_pods_list", "List pods")], raising=False)
    monkeypatch.setattr(incidents.agent, "sweep_rules", lambda: "operator rules", raising=False)
    monkeypatch.setattr(incidents.decide, "shadow", fake_shadow)
    monkeypatch.setattr(incidents.decide, "SHADOW", True)
    return calls


def test_shadow_compares_against_the_tool_the_agent_called_first(sweep, shadow):
    assert asyncio.run(incidents.sweep_once(None)) == "ok"
    assert len(shadow) == 2 and len(sweep["sent"]) == 2               # both alerts enriched AND shadowed
    call = shadow[0]
    assert call["actual"] == "k8s_pods_list"                           # read off the agent's own trace
    assert call["request"] == incidents._investigation_prompt(A)       # the SAME prompt the agent saw
    assert call["tools"] == [("k8s_pods_list", "List pods")] and call["rules"] == "operator rules"
    assert call["alert"] == "TargetDown"
    assert "k8s_pods_log" not in sweep["sent"][0][1]                   # the pick never reaches the digest


def test_no_shadow_call_when_the_sweep_defers(sweep, shadow):
    # a deferred alert is retried next sweep — asking the paid model now would pay twice for one comparison
    sweep["agent"] = incidents.agent.LocalUnavailable("busy")
    assert asyncio.run(incidents.sweep_once(None)) == "deferred"
    assert shadow == []


def test_no_shadow_call_when_the_enrichment_failed(sweep, shadow):
    # no trace → no baseline to compare with → nothing worth paying for
    sweep["agent"] = RuntimeError("fleet down")
    assert asyncio.run(incidents.sweep_once(None)) == "ok"
    assert shadow == [] and len(sweep["sent"]) == 2


def test_shadow_is_off_by_default_and_then_never_called(sweep, shadow, monkeypatch):
    monkeypatch.setattr(incidents.decide, "SHADOW", False)
    asyncio.run(incidents.sweep_once(None))
    assert shadow == [] and len(sweep["sent"]) == 2


# The secrets below are SYNTHETIC fixtures (the shapes the redaction must catch), marked `gitleaks:allow` on their line.
# --- B209 (2026-10-14): the sweep's digest is LLM text written from untrusted pod logs, sent to Telegram. Every OUTPUT
# validator in weyland-guard is SHADOW (record-only) and none detects secrets, so the operator redacts deterministically
# before sending, and a redaction failure drops the message instead of sending raw text (fail closed). -----------------
@pytest.mark.parametrize("secret", [
    "ghp_" + "A" * 36,                                        # GitHub classic token
    "github_pat_" + "B" * 22 + "_" + "C" * 59,                # GitHub fine-grained token
    "AKIA" + "ABCDEFGHIJKLMNOP",                              # AWS access key id
    "sk-ant-api03-" + "x" * 40,                               # Anthropic key
    "sk-" + "y" * 48,                                         # OpenAI-style key
    "xoxb-123456789012-123456789012-" + "z" * 24,             # Slack bot token  # gitleaks:allow (synthetic fixture)
    "123456789:" + "Q" * 35,                                  # Telegram bot token
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4In0.c2lnbmF0dXJlLXZhbHVl",   # a JWT
])
def test_redact_removes_known_token_shapes(secret):
    out = incidents._redact(f"the pod logged {secret} before it crashed")
    assert secret not in out and "[REDACTED]" in out
    assert out.startswith("the pod logged ") and out.endswith(" before it crashed")


def test_redact_keeps_the_key_name_but_drops_its_value():
    out = incidents._redact("env: PASSWORD=hunter2hunter2 api_key: abc123def456 token=t0k3n-value")  # gitleaks:allow (synthetic fixture)
    assert "hunter2hunter2" not in out and "abc123def456" not in out and "t0k3n-value" not in out
    assert "PASSWORD=" in out and "api_key:" in out and "token=" in out


def test_redact_drops_the_password_in_a_connection_url():
    out = incidents._redact("dsn postgresql://weyland:s3cretpw@weyland-postgres:5432/weyland failed")
    assert "s3cretpw" not in out and "postgresql://weyland:[REDACTED]@weyland-postgres:5432/weyland" in out


def test_redact_removes_a_private_key_block():
    block = "-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXktdjEAAAAA\n-----END OPENSSH PRIVATE KEY-----"  # gitleaks:allow (synthetic fixture)
    out = incidents._redact(f"found:\n{block}\ndone")
    assert "b3BlbnNzaC1rZXktdjEAAAAA" not in out and "[REDACTED]" in out and out.endswith("done")


def test_redact_leaves_ordinary_incident_text_alone():
    text = "PodCrashLooping on api-1: OOMKilled 3 times in 10m; memory limit 512Mi, last restart 14:02."
    assert incidents._redact(text) == text


def test_safe_digest_drops_the_message_when_redaction_fails(monkeypatch):
    def _boom(_text):
        raise RuntimeError("regex engine failure")
    monkeypatch.setattr(incidents, "_redact", _boom)
    assert incidents._safe_digest("anything") is None      # None = do not send; never the raw text


def test_safe_digest_returns_the_redacted_text():
    assert incidents._safe_digest("key ghp_" + "A" * 36) == "key [REDACTED]"


# --- every sweep outcome series exists at 0 before the first sweep (B207 cascade, 2026-10-21) ------------------------
# WeylandOperatorSweepDeferred is `increase(...{outcome="deferred"}[30m]) > 0`: a series created by its first .inc() is
# born at 1, which increase() cannot see, so the first deferral after a restart never paged. Read in a FRESH interpreter
# that only imported the module: in this process, earlier tests' sweeps would already have created some series.

def fresh_series(module, metric):
    """The label sets `metric` exports right after `import module`, nothing else run."""
    code = (f"import json, conftest, {module}; from prometheus_client import REGISTRY; "
            f"print(json.dumps([s.labels for m in REGISTRY.collect() for s in m.samples if s.name == '{metric}']))")
    out = subprocess.run([sys.executable, "-c", code], cwd=os.path.dirname(os.path.dirname(__file__)),
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


@pytest.mark.parametrize("outcome", ["ok", "deferred", "error", "digest_dropped", "digest_blocked"])
def test_every_sweep_outcome_series_exists_at_import(outcome):
    assert {"outcome": outcome} in fresh_series("incidents", "operator_incident_sweeps_total")
