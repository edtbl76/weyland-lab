"""Tests for realm_eval.py (B253, 2026-11-20) — the Realm of Agents evaluation driver.

Modes: plan (local: what runs next, resumable), run (in-cluster: POST /eval/run per item, one JSON line each),
judge-plan (local: the blind judge's inputs), judge (in-cluster: wl-judge-oss scores each answer against its rubric),
report (local: the tables). The rules under test:
  * the order interleaves arms per task (seeded), so a slow hour hits every arm alike, and a rerun resumes;
  * a failed run is RECORDED as a failure and scores 0, never dropped as missing (fail closed);
  * the judge never sees the arm (an opaque ref ties a score back), and an unparseable verdict is an error, not a score;
  * judge calls disable LiteLLM fallbacks, so the judge can never fall through to a paid model.
"""
import io
import json

import httpx
import pytest

import realm_eval as ev

TASKS = [
    {"id": "t1", "kind": "single", "q": "q1", "accept": ["saga"], "rubric": ["a", "b"]},
    {"id": "t2", "kind": "multi", "q": "q2", "accept": ["operator", "verdandi"], "rubric": ["c"]},
]


# --- plan ----------------------------------------------------------------------------------------------------------
def test_plan_covers_every_task_arm_and_rep_once():
    items = ev.plan(TASKS, done=set(), arms=ev.ARMS, reps=3)
    keys = [(i["id"], i["arm"], i["rep"]) for i in items]
    assert len(keys) == len(set(keys)) == 2 * 3 * 3
    assert all(i["q"] in ("q1", "q2") and i["kind"] in ("single", "multi") for i in items)


def test_plan_interleaves_arms_within_a_task_and_is_reproducible():
    a = ev.plan(TASKS, done=set(), arms=ev.ARMS, reps=1)
    assert [i["id"] for i in a[:3]] == ["t1"] * 3 and {i["arm"] for i in a[:3]} == set(ev.ARMS)
    assert a == ev.plan(TASKS, done=set(), arms=ev.ARMS, reps=1)   # seeded: the same order every time


def test_plan_resumes_and_limits():
    first = ev.plan(TASKS, done=set(), arms=ev.ARMS, reps=1, limit=4)
    done = {(i["id"], i["arm"], i["rep"]) for i in first}
    rest = ev.plan(TASKS, done=done, arms=ev.ARMS, reps=1)
    assert len(first) == 4 and len(rest) == 2 and not done & {(i["id"], i["arm"], i["rep"]) for i in rest}


def test_done_keys_reads_results_including_failures():
    lines = [json.dumps({"id": "t1", "arm": "realm", "rep": 1, "ok": True}),
             json.dumps({"id": "t1", "arm": "single", "rep": 1, "ok": False}), ""]
    assert ev.done_keys(lines) == {("t1", "realm", 1), ("t1", "single", 1)}


# --- run -----------------------------------------------------------------------------------------------------------
def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://realm")


def test_run_one_records_the_measurements():
    def h(req):
        body = json.loads(req.content)
        assert req.url.path == "/eval/run" and body == {"task": "q1", "arm": "routed"}
        return httpx.Response(200, json={"arm": "routed", "routed_to": "saga", "answer": "x", "seconds": 2.0,
                                         "input_tokens": 10, "output_tokens": 2, "llm_calls": 2, "tool_calls": 1,
                                         "delegations": 0, "tools_used": ["trino_list"], "delegated_to": []})
    rec = ev.run_one(_client(h), {"id": "t1", "arm": "routed", "rep": 2, "q": "q1", "kind": "single"})
    assert rec["ok"] is True and rec["routed_to"] == "saga" and rec["rep"] == 2 and rec["input_tokens"] == 10
    assert rec["wall_seconds"] >= 0


def test_run_one_records_an_http_failure_as_a_failure():
    rec = ev.run_one(_client(lambda req: httpx.Response(502, json={"detail": "eval run failed: boom"})),
                     {"id": "t1", "arm": "single", "rep": 1, "q": "q1", "kind": "single"})
    assert rec["ok"] is False and rec["status"] == 502 and "boom" in rec["error"] and rec["answer"] == ""


def test_run_one_records_a_timeout_as_a_failure():
    def h(req):
        raise httpx.ReadTimeout("slow", request=req)
    rec = ev.run_one(_client(h), {"id": "t1", "arm": "realm", "rep": 1, "q": "q1", "kind": "single"})
    assert rec["ok"] is False and rec["status"] is None and "slow" in rec["error"]


def test_an_empty_answer_is_a_failure():
    ok = {"arm": "single", "routed_to": None, "answer": "  ", "seconds": 1}
    rec = ev.run_one(_client(lambda req: httpx.Response(200, json=ok)),
                     {"id": "t1", "arm": "single", "rep": 1, "q": "q1", "kind": "single"})
    assert rec["ok"] is False and "empty" in rec["error"]


# --- judge ---------------------------------------------------------------------------------------------------------
def test_judge_plan_is_blind_and_skips_failures_and_scored():
    results = [{"id": "t1", "arm": "realm", "rep": 1, "ok": True, "answer": "A"},
               {"id": "t1", "arm": "single", "rep": 1, "ok": True, "answer": "B"},
               {"id": "t2", "arm": "routed", "rep": 1, "ok": False, "answer": ""}]
    scored = {ev.ref_of("t1", "single", 1)}
    items = ev.judge_plan(TASKS, results, scored)
    assert len(items) == 1
    item = items[0]
    assert set(item) == {"ref", "q", "rubric", "answer"} and item["answer"] == "A"
    assert "realm" not in json.dumps(item)   # nothing names the arm


def test_ref_is_opaque_and_stable():
    r = ev.ref_of("t1", "realm", 1)
    assert r == ev.ref_of("t1", "realm", 1) and "realm" not in r and r != ev.ref_of("t1", "single", 1)


@pytest.mark.parametrize("text", [
    '{"met": [true, false], "score": 3, "reason": "half"}',
    'Here you go:\n```json\n{"met": [true, false], "score": 3, "reason": "half"}\n```',
])
def test_parse_verdict_accepts_json_with_or_without_fences(text):
    v = ev.parse_verdict(text, n_criteria=2)
    assert v == {"met": [True, False], "score": 3, "reason": "half"}


@pytest.mark.parametrize("text", ["no json here", '{"met": [true], "score": 3}', '{"met": [true, true], "score": 9}',
                                  '{"met": [true, "yes"], "score": 3}'])
def test_parse_verdict_refuses_anything_malformed(text):
    with pytest.raises(ValueError):
        ev.parse_verdict(text, n_criteria=2)


def test_judge_one_sends_no_fallbacks_and_no_arm():
    seen = {}

    def h(req):
        seen.update(json.loads(req.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"met": [true, true], "score": 5, "reason": "ok"}'}}]})
    out = ev.judge_one(_client(h), {"ref": "r1", "q": "q1", "rubric": ["a", "b"], "answer": "A"}, model="wl-judge-oss")
    assert seen["disable_fallbacks"] is True and seen["model"] == "wl-judge-oss" and seen["temperature"] == 0
    assert out == {"ref": "r1", "ok": True, "met": [True, True], "score": 5, "reason": "ok"}
    assert "arm" not in json.dumps(seen["messages"]).lower()


def test_judge_one_records_a_bad_verdict_as_a_judge_error():
    h = lambda req: httpx.Response(200, json={"choices": [{"message": {"content": "I think it is fine"}}]})
    out = ev.judge_one(_client(h), {"ref": "r1", "q": "q1", "rubric": ["a"], "answer": "A"}, model="wl-judge-oss")
    assert out["ok"] is False and "error" in out


# --- report --------------------------------------------------------------------------------------------------------
def test_summarise_counts_failures_as_zero_and_routing_against_accept():
    results = [
        {"id": "t1", "arm": "realm", "rep": 1, "ok": True, "routed_to": "saga", "answer": "aaaa", "wall_seconds": 10,
         "input_tokens": 100, "output_tokens": 10, "tool_calls": 2, "delegations": 1, "llm_calls": 3},
        {"id": "t1", "arm": "realm", "rep": 2, "ok": False, "routed_to": None, "answer": "", "wall_seconds": 900,
         "error": "timeout"},
        {"id": "t2", "arm": "realm", "rep": 1, "ok": True, "routed_to": "tyr", "answer": "bb", "wall_seconds": 20,
         "input_tokens": 50, "output_tokens": 5, "tool_calls": 0, "delegations": 0, "llm_calls": 1},
    ]
    scores = {ev.ref_of("t1", "realm", 1): {"ok": True, "met": [True, False], "score": 4},
              ev.ref_of("t2", "realm", 1): {"ok": True, "met": [True], "score": 5}}
    s = ev.summarise(TASKS, results, scores)["realm"]
    assert s["runs"] == 3 and s["failures"] == 1
    assert s["rubric_mean"] == pytest.approx((0.5 + 0 + 1.0) / 3)
    assert s["by_kind"]["single"]["rubric_mean"] == pytest.approx(0.25)
    assert s["routing_accuracy"] == pytest.approx(1 / 2)   # t1 → saga ok; t2 → tyr not in accept; the failure unrouted
    assert s["misroutes"] == [("t2", "tyr")]
    assert s["tokens_mean"] == pytest.approx(82.5)          # over successful runs only


def test_summarise_refuses_an_unjudged_success():
    results = [{"id": "t1", "arm": "single", "rep": 1, "ok": True, "routed_to": None, "answer": "x", "wall_seconds": 1,
                "input_tokens": 1, "output_tokens": 1, "tool_calls": 0, "delegations": 0, "llm_calls": 1}]
    with pytest.raises(ValueError, match="unjudged"):
        ev.summarise(TASKS, results, {})


def test_read_jsonl_ignores_blank_lines_but_not_garbage():
    assert ev.read_jsonl(io.StringIO('{"a": 1}\n\n{"b": 2}\n')) == [{"a": 1}, {"b": 2}]
    with pytest.raises(ValueError):
        ev.read_jsonl(io.StringIO('{"a": 1}\nnot json\n'))
