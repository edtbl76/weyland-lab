"""The Hook/Decision wire contract between weyland-guard and its callers, now shared through grkit (B206 slice 2).

WHY THIS EXISTS. `weyland-tool-server` is an HTTP client of this service:

    _GUARD_PATHS = {Hook.INPUT: "/guard/input", Hook.OUTPUT: "/guard/output", Hook.ACT: "/guard/act"}
    ...
    return Verdict(v.get("validator", "guard"), Decision.BLOCK, v.get("score"), v.get("reason", ""), 0)

So `Hook`'s VALUES are the URL paths this service routes, `Decision`'s values are what the client parses out of this
service's JSON, and `Verdict` is built POSITIONALLY. Until 2026-10-15 each service carried its own byte-identical
`guardrails/verdict.py`, held together by this test and `scripts/check-verdict-sync.sh`. Both now import one module,
`grkit.verdict` (github.com/edtbl76/grkit, pinned to one commit; `scripts/tests/grkit-pin.bats` fails if the two
services ever pin different ones). Two copies can no longer drift, so what's left to pin is the contract itself: a
grkit release that renamed a Hook value or reordered Verdict's fields would break the tool-server silently, and
these tests make that loud at the pin bump.
"""
from pathlib import Path

from grkit.verdict import Decision, Hook, Mode, Verdict

_SERVICES = Path(__file__).resolve().parents[2]


def test_hook_values_are_the_guard_routes():
    """tool-server calls /guard/<hook value>; app.py routes exactly these."""
    assert {h.name: h.value for h in Hook} == {"INPUT": "input", "OUTPUT": "output", "ACT": "act"}


def test_decision_values_are_the_wire_strings():
    assert {d.name: d.value for d in Decision} == {"PASS": "pass", "FLAG": "flag", "BLOCK": "block"}


def test_mode_values_are_the_admin_toggle():
    assert {m.name: m.value for m in Mode} == {"OFF": "off", "SHADOW": "shadow", "FLAG": "flag", "BLOCK": "block"}


def test_verdict_field_order_is_positional_contract():
    """tool-server constructs Verdict(validator, decision, score, reason, latency_ms) positionally."""
    assert list(Verdict.__dataclass_fields__) == ["validator", "decision", "score", "reason", "latency_ms"]


def test_the_guard_response_shape_round_trips():
    """This service answers {decision, verdict:{validator, decision, score, reason, latency_ms}}; the client
    rebuilds the Verdict from the inner object."""
    wire = {"validator": "policy.gate", "decision": "block", "score": 0.97, "reason": "actor not allowlisted",
            "latency_ms": 12}
    v = Verdict.from_wire(wire)
    assert v == Verdict("policy.gate", Decision.BLOCK, 0.97, "actor not allowlisted", 12)
    assert v.to_wire() == wire


def test_no_service_carries_its_own_copy_any_more():
    """A local guardrails/verdict.py would shadow nothing (imports are grkit.verdict) but would invite a fork."""
    for svc in ("weyland-guard", "weyland-tool-server"):
        assert not (_SERVICES / svc / "guardrails" / "verdict.py").exists(), f"{svc} has a local verdict.py again"
