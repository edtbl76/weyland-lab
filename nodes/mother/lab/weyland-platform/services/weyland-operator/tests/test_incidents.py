"""Tests for the incident-sweep triage logic (B45, ENRICH-ONLY).

The sweep reads firing alerts from Prometheus and must (a) skip alerts that fire BY DESIGN so the digest stays
real-signal-only, (b) fingerprint each firing episode stably so it notifies once, and (c) build an enrich-only
investigation prompt that never asks the agent to act. Those decisions are the pure functions tested here; the
async Prometheus/agent/Telegram round-trips (stubbed siblings) are validated live.
"""
import asyncio

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
