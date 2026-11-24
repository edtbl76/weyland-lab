"""B256 (2026-11-23, owner: option A): Claude Code's own memory writes are stamped with provenance.

Claude Code writes memory as plain files into the shared store (its memory path is a symlink to it), so they bypass
the governed gateway that stamps every other agent's writes. `.claude/hooks/memory-provenance.py` (PostToolUse on
Write|Edit|MultiEdit) adds the same fields to the note it just wrote; `check-shared-memory.py` flags any note changed
after the switch-on time that carries no `updated_by`, which catches a write made around the hook (a Bash edit, another
tool) within the watchdog's 15 minutes.
"""
import importlib.util
import io
import json
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hook = _load("memory_provenance", ".claude/hooks/memory-provenance.py")
csm = _load("check_shared_memory_prov", "scripts/check-shared-memory.py")
NOW = "2026-11-24T05:00:00Z"


def _front(text):
    head = text.split("\n---\n", 1)[0]
    return dict(line.split(": ", 1) for line in head.splitlines()[1:] if ": " in line)


# --- the stamp ----------------------------------------------------------------------------------------------------
def test_a_new_note_gets_full_provenance():
    out = hook.stamp("---\nname: a\ndescription: d\n---\n\nbody\n", now=NOW, session="s1", person="emangini")
    f = _front(out)
    assert f["created_by"] == "agent:claude-code" and f["author_kind"] == "agent"
    assert f["created_at"] == f"'{NOW}'" and f["source"] == "session:s1"
    assert f["updated_by"] == "agent:claude-code" and f["on_behalf_of"] == "user:emangini"
    assert f["name"] == "a" and out.endswith("\n\nbody\n")


def test_an_existing_author_is_kept_and_only_the_update_is_stamped():
    text = "---\nname: a\ncreated_by: agent:codex\ncreated_at: '2026-11-22T09:00:00Z'\n---\nbody\n"
    f = _front(hook.stamp(text, now=NOW, session="s1", person="emangini"))
    assert f["created_by"] == "agent:codex" and f["created_at"] == "'2026-11-22T09:00:00Z'"
    assert f["updated_by"] == "agent:claude-code" and f["updated_at"] == f"'{NOW}'"


def test_stamping_twice_updates_in_place_without_duplicating_keys():
    once = hook.stamp("---\nname: a\n---\nbody\n", now=NOW, session="s1", person="emangini")
    twice = hook.stamp(once, now="2026-11-24T06:00:00Z", session="s2", person="emangini")
    assert twice.count("updated_by:") == 1 and "2026-11-24T06:00:00Z" in twice and twice.count("created_by:") == 1


def test_a_note_without_frontmatter_gets_one():
    out = hook.stamp("just text\n", now=NOW, session="s1", person="emangini")
    assert out.startswith("---\n") and _front(out)["created_by"] == "agent:claude-code" and out.endswith("just text\n")


# --- which writes are stamped ---------------------------------------------------------------------------------------
def test_only_notes_in_the_store_are_stamped(tmp_path):
    store = tmp_path / "store"
    (store / "_check").mkdir(parents=True)
    assert hook.should_stamp(str(store / "a.md"), str(store))
    assert hook.should_stamp(str(store / "task" / "b1" / "n.md"), str(store))
    for p in (store / "MEMORY.md", store / "MEMORY-catalog.md", store / "_check" / "x.md", store / "a.txt",
              tmp_path / "elsewhere.md"):
        assert not hook.should_stamp(str(p), str(store)), p


def test_the_hook_stamps_the_file_a_write_touched_and_ignores_others(tmp_path, monkeypatch):
    store = tmp_path / "store"; store.mkdir()
    note = store / "lesson.md"; note.write_text("---\nname: lesson\n---\nbody\n")
    other = tmp_path / "code.py"; other.write_text("x = 1\n")
    monkeypatch.setenv("MEMORY_PROVENANCE_DIR", str(store))
    for path in (note, other):
        event = {"session_id": "abc", "tool_name": "Write", "tool_input": {"file_path": str(path)}}
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(event)))
        assert hook.main() == 0
    assert "created_by: agent:claude-code" in note.read_text() and "source: session:abc" in note.read_text()
    assert other.read_text() == "x = 1\n"


def test_bad_input_is_silent_never_a_failure(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
    assert hook.main() == 0


# --- the watchdog check -------------------------------------------------------------------------------------------
def test_a_note_changed_after_the_cutoff_without_a_stamp_is_named(tmp_path):
    (tmp_path / "old.md").write_text("---\nname: old\n---\nbody\n")
    (tmp_path / "stamped.md").write_text("---\nname: s\nupdated_by: agent:claude-code\n---\nbody\n")
    (tmp_path / "bypass.md").write_text("---\nname: b\n---\nbody\n")
    (tmp_path / "MEMORY.md").write_text("index\n")
    os.utime(tmp_path / "old.md", (100, 100))
    problems = csm.provenance_problems(str(tmp_path), cutoff=1000)
    assert problems == ["bypass.md changed after provenance began with no updated_by (written around the hook?)"]
