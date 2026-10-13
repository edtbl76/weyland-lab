"""Tests for ai_session_feeder.py — the Claude-Code session cost/usage parser (B62 telemetry → Port).

The numbers this produces (turns, tokens, tool count, API-equivalent $) drive the ai-dev-usage catalog. A parsing
slip silently reports wrong cost/usage. Pure logic (stdlib only): a fixture JSONL transcript in → the aggregated
dict out; and the price tiers are asserted against the real PRICING table.
"""
import json

import ai_session_feeder as f


def test_price_tier_matches_by_substring_and_defaults_to_sonnet():
    assert f.price_tier("claude-opus-4") == f.PRICING["opus"]
    assert f.price_tier("claude-haiku-4-5") == f.PRICING["haiku"]
    assert f.price_tier("claude-sonnet-5") == f.PRICING["sonnet"]
    assert f.price_tier("gpt-4o") == f.PRICING["sonnet"]      # unknown → sonnet default
    assert f.price_tier(None) == f.PRICING["sonnet"]


def test_parse_session_aggregates_turns_tokens_tools_cost(tmp_path):
    p = tmp_path / "sess.jsonl"
    rows = [
        {"type": "user", "timestamp": "2026-09-16T10:00:00Z"},
        {"type": "assistant", "timestamp": "2026-09-16T10:01:00Z", "message": {
            "model": "claude-haiku-4", "usage": {"input_tokens": 1000, "output_tokens": 500,
            "cache_read_input_tokens": 200, "cache_creation_input_tokens": 100},
            "content": [{"type": "tool_use"}, {"type": "text"}]}},
        {"type": "assistant", "timestamp": "2026-09-16T10:02:00Z", "message": {
            "model": "claude-haiku-4", "usage": {"input_tokens": 0, "output_tokens": 100}}},
    ]
    p.write_text("\n".join(json.dumps(r) for r in rows))
    s = f.parse_session(str(p))
    assert s["user_turns"] == 1 and s["assistant_turns"] == 2
    assert s["input_tokens"] == 1000 and s["output_tokens"] == 600
    assert s["cache_read_tokens"] == 200 and s["cache_creation_tokens"] == 100
    assert s["total_tokens"] == 1600                 # fresh in+out; cache tracked separately
    assert s["tools_invoked"] == 1                   # only the tool_use block counts
    assert s["models"] == ["claude-haiku-4"]
    assert s["duration_minutes"] == 2.0
    # haiku (in,out,cache_read,cache_create) = (0.80, 4.0, 0.08, 1.00) per M tokens
    expected = round((1000 * 0.80 + 600 * 4.0 + 200 * 0.08 + 100 * 1.00) / 1_000_000, 2)
    assert s["api_equiv_value_usd"] == expected


def test_parse_session_skips_blank_and_malformed_lines(tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_text("\n\nnot-json-at-all\n"
                 + json.dumps({"type": "user", "timestamp": "2026-09-16T10:00:00Z"}) + "\n"
                 + json.dumps({"type": "assistant", "timestamp": "2026-09-16T10:00:30Z", "message": {}}))
    s = f.parse_session(str(p))
    assert s["user_turns"] == 1 and s["assistant_turns"] == 1   # bad/blank lines ignored, not fatal


def test_parse_session_with_no_timestamped_events_returns_none(tmp_path):
    p = tmp_path / "empty.jsonl"
    p.write_text("")
    assert f.parse_session(str(p)) is None


# --- B185 lane 1: per-issue attribution (2026-10-12) ------------------------------------------------------------
# Shapes OBSERVED in real logs (2026-10-12): tool results arrive as `type: user` records whose content is a list holding
# a `tool_result` block; injected notices arrive as `type: user` strings starting with `<task-notification>` /
# `<system-reminder>`; `custom-title` records carry the session name and are RE-LOGGED nearly every turn (3,447 times in
# one session); a conveyor run's prompt names no issue, but its `issue-readiness.sh EMA-###` Bash call does.

def _ts(minute, second=0):
    return f"2026-10-12T10:{minute:02d}:{second:02d}Z"


def _user(minute, text):
    return {"type": "user", "timestamp": _ts(minute), "message": {"content": text}}


def _asst(minute, out=100, text="", tool_cmd=None, sidechain=False):
    content = [{"type": "text", "text": text}]
    if tool_cmd:
        content.append({"type": "tool_use", "name": "Bash", "input": {"command": tool_cmd}})
    return {"type": "assistant", "timestamp": _ts(minute), "isSidechain": sidechain,
            "message": {"model": "claude-opus-5-5", "usage": {"output_tokens": out}, "content": content}}


def _tool_result(minute, text):
    return {"type": "user", "timestamp": _ts(minute),
            "message": {"content": [{"type": "tool_result", "content": text}]}}


def _session(tmp_path, rows):
    p = tmp_path / "s.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows))
    return f.parse_session(str(p))


def test_time_follows_the_issue_named_in_the_prompts(tmp_path):
    s = _session(tmp_path, [
        _user(0, "status?"), _asst(1),                                  # nothing named yet → unattributed
        _user(2, "let's start B185"), _asst(3), _asst(4),
        _user(5, "now EMA-243 please"), _asst(6),
        _asst(16),                                                      # a 10-minute gap: idle, counted nowhere
        _asst(17)])
    assert s["unattributed"]["active_minutes"] == 2.0                   # 0→1, 1→2
    assert s["issues"]["B185"]["active_minutes"] == 3.0                 # 2→3, 3→4, 4→5
    assert s["issues"]["EMA-243"]["active_minutes"] == 2.0              # 5→6, 16→17 (6→16 is idle)
    assert s["issues"]["B185"]["output_tokens"] == 200 and s["issues"]["B185"]["assistant_turns"] == 2
    assert s["human_prompts"] == 3
    assert s["issues"]["B185"]["first_at"] == _ts(2)                   # when it first became current (cycle time)
    assert s["issues"]["EMA-243"]["first_at"] == _ts(5)


def test_ids_in_tool_results_assistant_text_and_injected_notices_never_switch(tmp_path):
    s = _session(tmp_path, [
        _user(0, "start B185"), _asst(1, text="see also B179 and EMA-237"),
        _tool_result(2, "EMA-100 EMA-101 B204"),
        {"type": "user", "timestamp": _ts(3), "message": {"content": "<task-notification>B179 done</task-notification>"}},
        {"type": "user", "timestamp": _ts(4), "message": {"content": "<system-reminder>EMA-292</system-reminder>"}},
        _asst(5)])
    assert set(s["issues"]) == {"B185"} and s["issues"]["B185"]["active_minutes"] == 5.0
    assert s["human_prompts"] == 1


def test_a_conveyor_run_is_attributed_by_its_readiness_call(tmp_path):
    s = _session(tmp_path, [
        _user(0, "Using the Linear MCP, find the oldest open issue labelled agent-ready."),
        _asst(1, tool_cmd="cd /w && bash scripts/issue-readiness.sh EMA-292 --no-comment"),
        _asst(2), _asst(3)])
    assert s["issues"]["EMA-292"]["active_minutes"] == 2.0 and s["unattributed"]["active_minutes"] == 1.0


def test_a_prompt_naming_two_issues_does_not_switch(tmp_path):
    s = _session(tmp_path, [_user(0, "start B185"), _asst(1), _user(2, "compare B179 with B204"), _asst(3)])
    assert set(s["issues"]) == {"B185"} and s["issues"]["B185"]["active_minutes"] == 3.0


def test_a_repeated_session_title_never_pulls_attribution_back(tmp_path):
    title = lambda m, t: {"type": "custom-title", "timestamp": _ts(m), "customTitle": t}  # noqa: E731
    s = _session(tmp_path, [
        title(0, "B179 emdash-trials"), _asst(1),
        _user(2, "start B185"), title(2, "B179 emdash-trials"), _asst(3),   # the same title re-logged: no switch
        title(4, "B185 time tracking"), _asst(5)])                          # a CHANGED title switches
    assert s["issues"]["B179"]["active_minutes"] == 2.0
    assert s["issues"]["B185"]["active_minutes"] == 3.0


def test_sidechain_turns_count_tokens_but_not_time(tmp_path):
    s = _session(tmp_path, [_user(0, "start B185"), _asst(1), _asst(2, out=999, sidechain=True), _asst(3)])
    assert s["issues"]["B185"]["active_minutes"] == 3.0                 # 0→1→3 on the main thread
    assert s["issues"]["B185"]["output_tokens"] == 1199


def test_one_message_split_over_several_records_counts_its_usage_once(tmp_path):
    # Claude Code logs ONE record per content block, each repeating the message's full usage (observed 2026-10-12: 7,836
    # records for 3,146 messages, usage identical within every id) — summing per record overstated tokens and $ ~2.7x.
    usage = {"input_tokens": 10, "output_tokens": 500}
    rec = lambda m, blk: {"type": "assistant", "timestamp": _ts(m), "message": {  # noqa: E731
        "id": "msg_1", "model": "claude-haiku-4", "usage": usage, "content": [blk]}}
    s = _session(tmp_path, [_user(0, "start B185"),
                            rec(1, {"type": "text", "text": "x"}), rec(1, {"type": "tool_use", "input": {}}),
                            rec(1, {"type": "tool_use", "input": {}})])
    assert s["output_tokens"] == 500 and s["input_tokens"] == 10 and s["assistant_turns"] == 1
    assert s["usage_counted"] == "per-message"     # summaries written before 2026-10-12 lack this: they summed records
    assert s["tools_invoked"] == 2                                     # the blocks differ: each tool_use is real
    assert s["issues"]["B185"]["output_tokens"] == 500 and s["issues"]["B185"]["assistant_turns"] == 1


def test_an_attended_readiness_call_does_not_steal_the_current_issue(tmp_path):
    # Observed 2026-10-12: an attended session working on B185 ran `issue-readiness.sh EMA-292` to check the conveyor's
    # queue, and the next 3.5 h landed on EMA-292. The readiness marker is for a run that has named nothing yet.
    s = _session(tmp_path, [_user(0, "start B185"),
                            _asst(1, tool_cmd="bash scripts/issue-readiness.sh EMA-292"), _asst(2)])
    assert set(s["issues"]) == {"B185"} and s["issues"]["B185"]["active_minutes"] == 2.0


def test_subagent_logs_add_tokens_to_the_issue_current_when_they_started(tmp_path):
    # Subagents log to <session>/subagents/agent-*.jsonl (observed 2026-10-12; the main log holds 0 sidechain records),
    # so they were never counted. Their tokens belong to the issue the parent was on when it launched them; their time
    # overlaps the parent's and is not added.
    sub = tmp_path / "s" / "subagents"
    sub.mkdir(parents=True)
    agent = lambda m, out: {"type": "assistant", "timestamp": _ts(m), "isSidechain": True, "message": {  # noqa: E731
        "id": f"sub_{m}", "model": "claude-haiku-4", "usage": {"output_tokens": out}, "content": []}}
    (sub / "agent-a1.jsonl").write_text("\n".join(json.dumps(r) for r in [agent(3, 40), agent(30, 60)]))
    (sub / "agent-a2.jsonl").write_text(json.dumps(agent(7, 1000)))
    s = _session(tmp_path, [_user(0, "start B185"), _asst(1), _user(5, "now B179"), _asst(6), _asst(8)])
    assert s["issues"]["B185"]["output_tokens"] == 100 + 40 + 60      # a1 started at :03, under B185
    assert s["issues"]["B179"]["output_tokens"] == 200 + 1000          # a2 started at :07, under B179
    assert s["issues"]["B179"]["active_minutes"] == 3.0                # 5→6→8; the subagent adds no time
    assert s["output_tokens"] == 300 + 1100 and s["subagents"] == 2


def test_collect_includes_the_emdash_conveyor_worktrees(tmp_path, monkeypatch):
    run = tmp_path / "-home-edwardmangini-emdash-worktrees-weyland-93040a9c-emdash-da39df5f"
    run.mkdir()
    (run / "r.jsonl").write_text(json.dumps({"type": "user", "timestamp": _ts(0), "message": {"content": "x"}}))
    monkeypatch.setattr(f, "PROJECTS_ROOT", str(tmp_path))
    sessions = f.collect()
    assert [(s["project"], s["service"]) for s in sessions] == [("weyland-lab", "weyland-lab")]
