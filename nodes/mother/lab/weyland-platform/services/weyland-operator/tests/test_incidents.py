"""Tests for the incident-sweep triage logic (B45, ENRICH-ONLY).

The sweep reads firing alerts from Prometheus and must (a) skip alerts that fire BY DESIGN so the digest stays
real-signal-only, (b) fingerprint each firing episode stably so it notifies once, and (c) build an enrich-only
investigation prompt that never asks the agent to act. Those decisions are the pure functions tested here; the
async Prometheus/agent/Telegram round-trips (stubbed siblings) are validated live.
"""
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
