"""check-harness-budget.py (B255, 2026-11-20): the instruction text every Claude Code session in this repo loads stays
within a budget, so the trims of 2026-11-20 (compact instructions in, AI-DLC ambient import cut, memory index split)
do not creep back. It follows Claude Code's own loading rules: CLAUDE.md and its @-imports (recursive, relative to the
importing file, each file counted once), every .claude/rules/*.md without a `paths:` scope, HTML comments stripped
(Claude Code strips them before loading, so they cost nothing); plus the descriptions of project skills and agents.
"""
import importlib.util
import pathlib

_PATH = pathlib.Path(__file__).resolve().parents[1] / "check-harness-budget.py"
_spec = importlib.util.spec_from_file_location("check_harness_budget", _PATH)
hb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hb)


def _repo(tmp_path, files):
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return str(tmp_path)


def test_imports_are_followed_recursively_and_counted_once(tmp_path):
    root = _repo(tmp_path, {"CLAUDE.md": "hi\n@AGENTS.md\n@AGENTS.md\n", "AGENTS.md": "rules\n@docs/x.md\n",
                            "docs/x.md": "xx\n"})
    loaded = hb.loaded_files(root)
    assert [p for p, _ in loaded] == ["CLAUDE.md", "AGENTS.md", "docs/x.md"]


def test_html_comments_cost_nothing(tmp_path):
    root = _repo(tmp_path, {"CLAUDE.md": "<!-- a long\nexplanation -->\nreal\n"})
    assert dict(hb.loaded_files(root))["CLAUDE.md"] == len("\nreal\n".encode())


def test_unscoped_rules_load_and_path_scoped_rules_do_not(tmp_path):
    root = _repo(tmp_path, {"CLAUDE.md": "x\n",
                            ".claude/rules/always.md": "@../../m/team.md\n",
                            ".claude/rules/scoped.md": "---\npaths:\n  - src/**\n---\nonly for src\n",
                            "m/team.md": "tdd\n"})
    names = [p for p, _ in hb.loaded_files(root)]
    assert ".claude/rules/always.md" in names and "m/team.md" in names and ".claude/rules/scoped.md" not in names


def test_skill_and_agent_descriptions_are_measured(tmp_path):
    root = _repo(tmp_path, {"CLAUDE.md": "x\n",
                            ".claude/skills/a/SKILL.md": "---\nname: a\ndescription: does a thing\n---\nbody\n",
                            ".claude/agents/b.md": "---\nname: b\ndescription: reviews\nmodel: x\n---\nbody\n"})
    assert hb.description_bytes(root, "skills") == len("does a thing") and hb.description_bytes(root, "agents") == len("reviews")


def test_within_budget_is_clean_and_over_budget_is_named(tmp_path):
    root = _repo(tmp_path, {"CLAUDE.md": "x" * 50 + "\n"})
    assert hb.problems(root, {"instructions_total": 100, "files": {}, "skills": 10, "agents": 10}) == []
    out = hb.problems(root, {"instructions_total": 10, "files": {"CLAUDE.md": 20}, "skills": 10, "agents": 10})
    assert any("CLAUDE.md is 51 bytes, over its 20-byte budget" in p for p in out)
    assert any("instructions total 51 bytes, over its 10-byte budget" in p for p in out)


def test_a_missing_claude_md_is_an_error_not_a_pass(tmp_path):
    root = _repo(tmp_path, {"AGENTS.md": "x\n"})
    assert hb.main(["--root", root]) == 2


def test_a_dangling_import_is_named(tmp_path):
    root = _repo(tmp_path, {"CLAUDE.md": "@missing.md\n"})
    assert any("missing.md" in p and "does not exist" in p
               for p in hb.problems(root, {"instructions_total": 100, "files": {}, "skills": 10, "agents": 10}))
