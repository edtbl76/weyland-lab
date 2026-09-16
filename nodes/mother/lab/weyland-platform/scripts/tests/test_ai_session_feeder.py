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
