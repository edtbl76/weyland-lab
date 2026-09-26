"""Validate the Bifrost Skills registry SoT (register_bifrost_skills.py).

The `SKILLS` list is the git source of truth for the Bifrost Skills Repository. A malformed entry (a non-kebab
name, an empty body, a DUPLICATE name) breaks the idempotent register at runtime — a duplicate is exactly what
produced the "skill name already exists" run on 2026-09-23. This guards the list's shape, and by importing the
module it also exercises the module-level data (so the script counts toward coverage instead of sitting at 0% and
regressing the ratchet). `httpx` is lazy-imported inside `main()`, so importing here needs no network deps.
"""
import re

import register_bifrost_skills as reg   # conftest.py puts scripts/ on sys.path (bare-name import, as the script runs)

_KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def test_skills_list_is_wellformed():
    skills = reg.SKILLS
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
    names = [s[0] for s in reg.SKILLS]
    dupes = sorted({n for n in names if names.count(n) > 1})
    assert not dupes, f"duplicate skill names: {dupes}"


def test_loop_skills_are_present():
    # The B175 loop-library seed — guard that the four loop-shaped skills stay registered.
    names = {s[0] for s in reg.SKILLS}
    expected = {"dod-gate", "master-the-tool-walk", "pr-lifecycle-reconcile", "full-guard-suite-preship"}
    assert expected <= names, f"missing loop skills: {sorted(expected - names)}"
