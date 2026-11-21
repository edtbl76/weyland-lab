"""The two-tier memory index (B255, 2026-11-20).

`MEMORY.md` is the small core every Claude Code session loads (Claude Code loads only its first 25 KB / 200 lines, and
silently drops the rest), so it has a budget. `MEMORY-catalog.md` lists every note by topic and is read on demand.
`index_problems` is the check: the core exists and is within budget, every note is linked from the core or the catalog,
and no link points at a missing note. check-shared-memory.py runs it in every mode, the 15-minute watchdog included.
"""
import importlib.util
import pathlib

_PATH = pathlib.Path(__file__).resolve().parents[1] / "check-shared-memory.py"
_spec = importlib.util.spec_from_file_location("check_shared_memory", _PATH)
csm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(csm)


def _store(tmp_path, core, catalog, notes):
    for n in notes:
        p = tmp_path / n
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("---\nname: x\n---\nbody\n")
    if core is not None:
        (tmp_path / "MEMORY.md").write_text(core)
    if catalog is not None:
        (tmp_path / "MEMORY-catalog.md").write_text(catalog)
    return str(tmp_path)


def test_a_complete_store_within_budget_has_no_problems(tmp_path):
    d = _store(tmp_path, "- [a](a.md)\n", "- [a](a.md) · [b](b.md) · [c](sub/c)\n", ["a.md", "b.md", "sub/c.md"])
    assert csm.index_problems(d) == []


def test_a_note_linked_from_neither_file_is_named(tmp_path):
    d = _store(tmp_path, "- [a](a.md)\n", "- [a](a.md)\n", ["a.md", "orphan.md"])
    assert csm.index_problems(d) == ["orphan.md is in neither MEMORY.md nor MEMORY-catalog.md"]


def test_a_core_over_budget_is_named_with_its_size(tmp_path):
    big = "- [a](a.md) " + "x" * 200 + "\n"
    d = _store(tmp_path, big, "- [a](a.md)\n", ["a.md"])
    problems = csm.index_problems(d, budget=100)
    assert len(problems) == 1 and "MEMORY.md is" in problems[0] and "over its 100-byte budget" in problems[0]


def test_a_link_to_a_missing_note_is_named(tmp_path):
    d = _store(tmp_path, "- [a](a.md)\n", "- [a](a.md) · [gone](gone.md)\n", ["a.md"])
    assert csm.index_problems(d) == ["MEMORY-catalog.md links gone.md, which does not exist"]


def test_a_missing_core_is_a_problem_not_a_pass(tmp_path):
    d = _store(tmp_path, None, "- [a](a.md)\n", ["a.md"])
    assert "MEMORY.md is missing" in csm.index_problems(d)[0]


def test_an_empty_store_is_a_problem_not_a_pass(tmp_path):
    d = _store(tmp_path, "", "", [])
    assert csm.index_problems(d) == ["no notes found: the index check would pass vacuously"]


def test_the_default_budget_is_half_claude_codes_cap():
    assert csm.CORE_BUDGET_BYTES == 12 * 1024
