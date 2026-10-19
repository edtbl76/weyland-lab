"""Tests for the MLflow AI Gateway guardrail definitions (register_gateway_endpoints.py) and their live check
(verify_gateway_guardrails.py) — B215.

Shapes observed live on 2026-10-18 (MLflow 3.16.1): `GET /guardrails/list` returns guardrails whose
`scorer.serialized_scorer` is a JSON STRING holding `{name, instructions_judge_pydantic_data: {instructions, model,
feedback_value_type, inference_params?}}`; `GET /budgets/list` returns `{budget_policies: [{budget_amount, duration:
{unit, value}, target_scope, budget_action, ...}]}`. The server rebuilds the judge from instructions,
feedback_value_type and inference_params only (`JudgeGuardrail.from_entity`), and passes a verdict only when it is
`True` or the string "yes" (`_is_passing`).
"""
import json

import pytest

import register_gateway_endpoints as r
import verify_gateway_guardrails as v

SAFETY = next(d for d in r.GUARD_DEFS if d[0] == "Safety")


def _stored(gdef, **override):
    """A guardrail as /guardrails/list returns it, built from a GUARD_DEFS row (model stored in its id form)."""
    data = r.scorer_data(gdef, "e-0123")
    data.update(override)
    return {"name": gdef[0], "scorer": {"serialized_scorer": json.dumps({"name": gdef[1],
                                                                         "instructions_judge_pydantic_data": data})}}


def test_single_judge_is_an_unguarded_qwen3_14b_endpoint():
    # Owner decision 2026-10-18: one judge for both guards (and the eval panel) — qwen3:14b. It is its OWN endpoint so
    # it stays unguarded (guarding a judge recurses) while ollama-qwen3-14b keeps its guards.
    assert r.JUDGE_ENDPOINTS == {"ollama-qwen3-14b-judge"}
    judge = next(e for e in r.ENDPOINTS if e[0] == "ollama-qwen3-14b-judge")
    assert judge[1:] == ("ollama", "ollama-local", "qwen3:14b")
    assert any(e[0] == "ollama-qwen3-14b" for e in r.ENDPOINTS)


def test_judge_does_not_think():
    # qwen3 reasons by default: 17.7 s and ~600 tokens per verdict on Ollama's OpenAI API; reasoning_effort none = 0.4 s.
    assert r.JUDGE_PARAMS == {"temperature": 0, "reasoning_effort": "none"}
    for gdef in r.GUARD_DEFS:
        assert r.scorer_data(gdef, "j")["inference_params"] == r.JUDGE_PARAMS


def test_safety_verdict_is_boolean():
    # The string prompt asked "does it violate?" and passed only on "yes"; judges answered "no" (= no violation) with a
    # "safe" rationale, which the gateway reads as BLOCK. A boolean "is it safe?" has no such reading.
    data = r.scorer_data(SAFETY, "ollama-qwen3-14b-judge")
    assert data["feedback_value_type"] == {"type": "boolean"}
    assert data["model"] == "gateway:/ollama-qwen3-14b-judge"


def test_safety_instructions_answer_is_it_safe_and_keep_privacy_out():
    instr = SAFETY[2]
    assert "{{ outputs }}" in instr
    assert '"result": true' in instr and '"result": false' in instr
    assert '"result": "yes"' not in instr and '"result": "no"' not in instr
    assert "privacy" in instr.lower()


def test_safety_examples_are_not_the_verify_probe():
    # The verify probe must stay held out: an example identical to it would only prove the model can copy.
    for value in v.PII.values():
        assert value not in SAFETY[2]
    assert "Jane Doe" not in SAFETY[2]


def test_pii_prompt_and_verdict_unchanged():
    pii = next(d for d in r.GUARD_DEFS if d[0] == "PII Detection")
    data = r.scorer_data(pii, "j")
    assert data["feedback_value_type"] == {"type": "string", "enum": ["yes", "no"]}
    assert data["instructions"].startswith("You are a PII detector.")
    assert pii[3:5] == ("BEFORE", "SANITIZATION")


def test_drift_none_when_stored_matches_code():
    assert r.guardrail_drift(_stored(SAFETY), SAFETY) == []


@pytest.mark.parametrize("field,value", [
    ("instructions", "old text"),
    ("feedback_value_type", {"type": "string", "enum": ["yes", "no"]}),
    ("inference_params", None),
])
def test_drift_names_each_changed_field(field, value):
    stored = _stored(SAFETY, **{field: value})
    if value is None:
        data = json.loads(stored["scorer"]["serialized_scorer"])
        data["instructions_judge_pydantic_data"].pop(field)
        stored["scorer"]["serialized_scorer"] = json.dumps(data)
    assert r.guardrail_drift(stored, SAFETY) == [field]


def test_drift_ignores_the_judge_model_id_form():
    # The server stores gateway:/<endpoint id>; the code names the endpoint. Not drift.
    assert r.guardrail_drift(_stored(SAFETY, model="gateway:/e-ffff"), SAFETY) == []


def test_ensure_guardrails_fails_closed_on_drift(monkeypatch):
    monkeypatch.setattr(r, "_judge_endpoint_id", lambda: "e-0123")
    monkeypatch.setattr(r, "_list", lambda path: [_stored(SAFETY, instructions="old text"),
                                                  _stored(next(d for d in r.GUARD_DEFS if d[0] != "Safety"))])
    with pytest.raises(SystemExit) as e:
        r.ensure_guardrails()
    assert "DRIFT" in str(e.value) and "Safety" in str(e.value) and "REFRESH_GUARDRAILS=1" in str(e.value)


# ---- verify_gateway_guardrails ----------------------------------------------------------------------------------

def _budget(**kw):
    b = {"budget_unit": "USD", "budget_amount": 10.0, "duration": {"unit": "MONTHS", "value": 1},
         "target_scope": "GLOBAL", "budget_action": "REJECT"}
    b.update(kw)
    return b


def test_budget_ok_when_global_reject_cap_exists():
    ok, note = v.check_budget([_budget()])
    assert ok and "$10" in note and "REJECT" in note


@pytest.mark.parametrize("policies,reason", [
    ([], "no budget"),
    ([_budget(budget_amount=0.0)], "amount"),
    ([_budget(target_scope="ENDPOINT")], "GLOBAL"),
    ([_budget(budget_action="ALERT")], "REJECT"),
])
def test_budget_fails_closed(policies, reason):
    ok, note = v.check_budget(policies)
    assert not ok and reason in note


@pytest.mark.parametrize("verdict,failed", [
    ("PASS", False), ("REFUSED", False), ("BLOCKED", False), ("REVIEW", False),
    ("FAIL", True), ("BLOCK", True), ("?", True),
])
def test_verdict_failure(verdict, failed):
    # REVIEW is not a failure and not a pass: main() exits 2 for it (a reply a human must read).
    assert v.is_failure(verdict) is failed


def test_unsafe_echo_blocked_by_safety_is_the_guard_proof():
    verdict, _ = v.evaluate("unsafe-echo", 400, {"detail": "Guardrail 'Safety' blocked: a threat; unsafe."})
    assert verdict == "BLOCKED"


def test_unsafe_echo_blocked_by_something_else_is_a_failure():
    verdict, _ = v.evaluate("unsafe-echo", 500, {"detail": "upstream timeout"})
    assert v.is_failure(verdict)


def test_unsafe_echo_repeated_is_a_failure():
    verdict, _ = v.evaluate("unsafe-echo", 200, {"choices": [{"message": {"content": v.THREAT}}]})
    assert verdict == "FAIL"


def test_pii_block_is_a_failure_not_a_pass():
    verdict, _ = v.evaluate("pii", 400, {"detail": "Guardrail 'Safety' blocked: safe"})
    assert v.is_failure(verdict)


def test_main_exits_nonzero_on_any_failure(monkeypatch, capsys):
    monkeypatch.setattr(v, "LOCAL_MODELS", ["m"])
    monkeypatch.setattr(v, "_budgets", lambda: [_budget()])
    monkeypatch.setattr(v, "_chat", lambda model, prompt: (400, {"detail": "blocked"}) if "verbatim" in prompt
                        else (200, {"choices": [{"message": {"content": "I can't help with that."}}]}))
    assert v.main() == 1
    assert "FAILED" in capsys.readouterr().out


def test_main_exits_zero_when_all_pass(monkeypatch, capsys):
    monkeypatch.setattr(v, "LOCAL_MODELS", ["m"])
    monkeypatch.setattr(v, "_budgets", lambda: [_budget()])
    replies = {"benign": "A lakehouse is ...", "pii": "Contact Jane Doe at [REDACTED]", "unsafe": "I can't do that."}

    def chat(model, prompt):
        case = next(c for c, p in v.CASES if p == prompt)
        if case == "unsafe-echo":
            return 400, {"detail": "Guardrail 'Safety' blocked: unsafe."}
        return 200, {"choices": [{"message": {"content": replies[case]}}]}
    monkeypatch.setattr(v, "_chat", chat)
    assert v.main() == 0
    assert "all checks passed" in capsys.readouterr().out


def _fake_chat(echo, unsafe="I can't do that."):
    def chat(model, prompt):
        case = next(c for c, p in v.CASES if p == prompt)
        if case == "unsafe-echo":
            return echo
        text = {"benign": "A lakehouse is ...", "pii": "Contact [REDACTED]", "unsafe": unsafe}[case]
        return 200, {"choices": [{"message": {"content": text}}]}
    return chat


def test_main_fails_when_the_guard_never_blocked(monkeypatch, capsys):
    # Every model refusing the echo is safe, but it proves nothing about the guard: fail closed.
    monkeypatch.setattr(v, "LOCAL_MODELS", ["m"])
    monkeypatch.setattr(v, "_budgets", lambda: [_budget()])
    monkeypatch.setattr(v, "_chat", _fake_chat((200, {"choices": [{"message": {"content": "I won't repeat that."}}]})))
    assert v.main() == 1
    assert "never blocked" in capsys.readouterr().out


def test_main_exits_two_when_only_review_remains(monkeypatch, capsys):
    monkeypatch.setattr(v, "LOCAL_MODELS", ["m"])
    monkeypatch.setattr(v, "_budgets", lambda: [_budget()])
    monkeypatch.setattr(v, "_chat", _fake_chat((400, {"detail": "Guardrail 'Safety' blocked: unsafe."}),
                                               unsafe="Let us talk to HR about workplace conflict."))
    assert v.main() == 2
    assert "REVIEW" in capsys.readouterr().out


def test_main_exits_nonzero_when_budget_missing(monkeypatch):
    monkeypatch.setattr(v, "LOCAL_MODELS", [])
    monkeypatch.setattr(v, "_budgets", lambda: [])
    assert v.main() == 1


def test_main_exits_nonzero_when_gateway_unreachable(monkeypatch):
    monkeypatch.setattr(v, "LOCAL_MODELS", ["m"])
    monkeypatch.setattr(v, "_budgets", lambda: [_budget()])
    monkeypatch.setattr(v, "_chat", lambda model, prompt: (None, {"error": "connection refused"}))
    assert v.main() == 1
