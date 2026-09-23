"""Validate the Bifrost Skills registry SoT (scripts/register_bifrost_skills.py).

The register script's `SKILLS` list is the git source of truth for the Bifrost Skills Repository. A malformed
entry (a non-kebab name, an empty body, a DUPLICATE name) breaks the idempotent register at runtime — a duplicate
is exactly what produced the "skill name already exists" run on 2026-09-23. This test guards the list's shape, and
by importing the module it also exercises the module-level data (so the script counts toward coverage rather than
sitting at 0% and dragging the ratchet). `httpx` is lazy-imported inside `main()`, so importing here needs no deps
and never opens a network client.
"""
import importlib.util
import re
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "register_bifrost_skills.py"
_KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _load():
    spec = importlib.util.spec_from_file_location("register_bifrost_skills", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)   # runs module top-level (imports os, defines SKILLS) — no network, no httpx
    return mod


def test_skills_list_is_wellformed():
    mod = _load()
    skills = mod.SKILLS
    assert skills, "SKILLS is empty"
    for entry in skills:
        assert len(entry) == 4, f"skill tuple must be (name, category, description, body): {entry[:1]}"
        name, category, description, body = entry
        assert _KEBAB.match(name), f"skill name is not kebab-case: {name!r}"
        assert category.strip(), f"{name}: empty category"
        assert description.strip(), f"{name}: empty description"
        assert body.strip(), f"{name}: empty body"


def test_skill_names_are_unique():
    # A duplicate name makes the register POST collide ("already exists") — fail here, not at deploy time.
    names = [s[0] for s in _load().SKILLS]
    dupes = sorted({n for n in names if names.count(n) > 1})
    assert not dupes, f"duplicate skill names: {dupes}"


def test_loop_skills_are_present():
    # The B175 loop-library seed — guard that the four loop-shaped skills stay registered.
    names = {s[0] for s in _load().SKILLS}
    expected = {"dod-8-pillar-gate", "master-the-tool-walk", "pr-lifecycle-reconcile", "full-guard-suite-preship"}
    assert expected <= names, f"missing loop skills: {sorted(expected - names)}"
