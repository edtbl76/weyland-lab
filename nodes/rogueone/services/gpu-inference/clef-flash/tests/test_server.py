"""Tests for the on-demand Clef-flash server (B174): the request contract it enforces and how it reports failure.

The model itself is not loaded here (torch/transformers, ~8.5 GB of VRAM) — `handle` takes the decision function as an
argument, so these tests drive it with fakes. The real model is exercised by `scripts/clef-flash.sh smoke`.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server  # noqa: E402

GOOD = {"model": "clef-flash", "state": "orders are failing",
        "questions": {"team": {"type": "choice", "criteria": {"billing": "payments", "technical": "outages"}}}}


def _answer(_request):
    return {"model": "clef-flash", "answers": {"team": {"choice": "technical", "confidence": 0.9}},
            "usage": {"input_tokens": 12, "output_tokens": 0}}


def test_a_valid_request_returns_the_models_answer():
    status, body = server.handle(json.dumps(GOOD).encode(), _answer)
    assert status == 200 and body["answers"]["team"]["choice"] == "technical"


def test_malformed_json_is_400_and_never_reaches_the_model():
    called = []
    status, body = server.handle(b"{not json", lambda r: called.append(r))
    assert status == 400 and "JSON" in body["error"] and called == []


def test_a_request_without_questions_is_400():
    for bad in ({"state": "x"}, {"state": "x", "questions": {}}, {"state": "x", "questions": []}, ["a"]):
        status, body = server.handle(json.dumps(bad).encode(), _answer)
        assert status == 400, bad


def test_a_request_without_state_is_400():
    status, _body = server.handle(json.dumps({"questions": GOOD["questions"]}).encode(), _answer)
    assert status == 400


def test_an_oversized_body_is_413():
    status, _body = server.handle(b"x" * (server.MAX_BODY + 1), _answer)
    assert status == 413


def test_a_model_failure_is_500_with_the_reason_not_a_fake_answer():
    def boom(_request):
        raise RuntimeError("CUDA out of memory")
    status, body = server.handle(json.dumps(GOOD).encode(), boom)
    assert status == 500 and "CUDA out of memory" in body["error"] and "answers" not in body


def test_the_revision_is_pinned_to_a_full_commit():
    # the server imports and EXECUTES the model repo's Python — a moving branch would run unreviewed code
    assert len(server.REVISION) == 40 and all(c in "0123456789abcdef" for c in server.REVISION)
