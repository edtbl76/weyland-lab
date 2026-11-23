"""B256: the Basic Memory adapter behind governed writes. A missing note is "no note" (create may go ahead); any other
error, an unreachable store included, is raised: unreachable is never "no memory". Call shapes were observed on the live
server (write_note with metadata; edit_note append by file path; read_content's raw `text`)."""
import asyncio
import json
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import governed_store as gs


def _store(responses):
    calls = []

    async def call(name, args):
        calls.append((name, args))
        r = responses[name]
        if isinstance(r, Exception):
            raise r
        return r
    return gs.BasicMemoryStore(call), calls


def _text(payload):
    return types.SimpleNamespace(structured_content=None, content=[types.SimpleNamespace(text=json.dumps(payload))])


def test_read_returns_the_raw_text():
    s, calls = _store({"read_content": _text({"type": "text", "text": "---\na: b\n---\nbody"})})
    assert asyncio.run(s.read_raw("task/x/n.md")) == "---\na: b\n---\nbody"
    assert calls == [("read_content", {"path": "task/x/n.md"})]


def test_a_missing_note_is_none():
    s, _ = _store({"read_content": gs.ToolError("Resource not found: task/x/n.md")})
    assert asyncio.run(s.read_raw("task/x/n.md")) is None


def test_any_other_error_is_raised_not_treated_as_missing():
    s, _ = _store({"read_content": ConnectionError("rogueone unreachable")})
    with pytest.raises(ConnectionError):
        asyncio.run(s.read_raw("task/x/n.md"))
    s, _ = _store({"read_content": gs.ToolError("internal error")})
    with pytest.raises(gs.ToolError):
        asyncio.run(s.read_raw("task/x/n.md"))


def test_write_and_append_use_the_observed_call_shapes():
    s, calls = _store({"write_note": _text({}), "edit_note": _text({})})
    assert asyncio.run(s.write("n", "task/x", "body", {"created_by": "agent:codex"}, False)) == "task/x/n.md"
    assert asyncio.run(s.append("task/x/n.md", "more", {"updated_by": "agent:codex"})) == "task/x/n.md"
    assert calls == [("write_note", {"title": "n", "directory": "task/x", "content": "body",
                                     "metadata": {"created_by": "agent:codex"}, "overwrite": False}),
                     ("edit_note", {"identifier": "task/x/n.md", "operation": "append", "content": "more",
                                    "metadata": {"updated_by": "agent:codex"}})]


def test_project_root_writes_use_the_root_directory():
    s, calls = _store({"write_note": _text({})})
    assert asyncio.run(s.write("a lesson", "", "body", {}, False)) == "a lesson.md"
    assert calls[0][1]["directory"] == "/"
