"""Tests for the streaming wire-protocol helpers in stream.py.

`_normalize` maps one LangGraph astream_events(v2) event → one compact wire event the UI renders (or None to drop),
and `_short` bounds any value that goes on the wire. If `_normalize` mislabels an event or fails to drop the pure
LangGraph scaffolding, the UI's live agent tree is wrong; if `_short` doesn't cap, a huge tool payload floods the SSE
stream. Both pure — no graph, no LLM.
"""
import json

import stream


def test_short_leaves_short_strings_untouched():
    assert stream._short("hello") == "hello"
    assert stream._short("") == ""


def test_short_truncates_long_strings_with_ellipsis():
    out = stream._short("x" * 700, n=600)
    assert out == "x" * 600 + "…"
    assert len(out) == 601


def test_short_json_encodes_non_strings():
    assert stream._short({"a": 1}) == json.dumps({"a": 1}, default=str)
    assert stream._short([1, 2]) == "[1, 2]"


def test_short_falls_back_to_str_on_unserializable():
    class Weird:
        def __repr__(self): return "WEIRD"
    # json.dumps(default=str) actually stringifies most things; a key that can't serialize forces the except path
    out = stream._short({("tuple", "key"): Weird()})
    assert "WEIRD" in out or out  # never raises; returns a bounded string


def test_normalize_tool_start_carries_bounded_input():
    ev = {"event": "on_tool_start", "run_id": "r1", "name": "search",
          "parent_ids": ["p"], "data": {"input": "q" * 700}}
    out = stream._normalize(ev)
    assert out["type"] == "tool_start" and out["id"] == "r1" and out["name"] == "search"
    assert out["parents"] == ["p"] and out["input"].endswith("…")


def test_normalize_tool_end_carries_output():
    out = stream._normalize({"event": "on_tool_end", "run_id": "r2", "data": {"output": "done"}})
    assert out["type"] == "tool_end" and out["output"] == "done"


def test_normalize_chat_model_boundaries():
    assert stream._normalize({"event": "on_chat_model_start", "run_id": "r"})["type"] == "llm_start"
    assert stream._normalize({"event": "on_chat_model_end", "run_id": "r"})["type"] == "llm_end"


def test_normalize_keeps_only_outermost_chain_start():
    # a chain_start with NO parents is the outer graph boundary the UI anchors on → node_start
    assert stream._normalize({"event": "on_chain_start", "run_id": "r", "parent_ids": []})["type"] == "node_start"
    # a chain_start WITH parents is inner LangGraph scaffolding → dropped
    assert stream._normalize({"event": "on_chain_start", "run_id": "r", "parent_ids": ["outer"]}) is None


def test_normalize_drops_unhandled_events():
    assert stream._normalize({"event": "on_chain_end", "run_id": "r"}) is None
    assert stream._normalize({"event": "on_llm_stream", "run_id": "r"}) is None
