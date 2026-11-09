#!/usr/bin/env python3
"""Generate or check the weyland-capabilities Agent Skill (B241) from capabilities.yaml + repos.yaml.

  usage: capabilities-skill.py --write            validate, then rewrite the generated block in register_bifrost_skills.py
         capabilities-skill.py --check            validate, and fail if that block differs (CI repo-guards)
         capabilities-skill.py --show             print the rendered skill body (what an agent will read)
         capabilities-skill.py --install          write ~/.agents/skills/weyland-capabilities/SKILL.md and link it from
                                                  ~/.claude/skills and ~/.codex/skills (rogueone, per user)
         capabilities-skill.py --check-installed  fail if the installed skill is missing or stale (run on rogueone)

Exit 0 in sync / written; 1 the registry is invalid, or the block or installed skill is stale; 2 a file is missing.
Runbook: docs/runbooks/weyland-capabilities.md.
"""
import argparse
import os
import sys
from pathlib import Path

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import capabilities_skill as cs  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
REGISTER = REPO / "nodes/mother/lab/weyland-platform/services/weyland-dagster/scripts/register_bifrost_skills.py"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--show", action="store_true")
    mode.add_argument("--install", action="store_true")
    mode.add_argument("--check-installed", action="store_true")
    a = ap.parse_args()
    loaded = _load()
    if isinstance(loaded, int):
        return loaded
    caps, repos = loaded
    if a.show:
        sys.stdout.write(cs.render(caps, repos))
        return 0
    if a.install or a.check_installed:
        return _installed(caps, repos, install=a.install)
    return _register_block(caps, repos, write=a.write)


def _load():
    """(caps, repos), or an exit code when a file is missing (2) or the registry is invalid (1)."""
    paths = [REPO / "capabilities.yaml", REPO / "repos.yaml", REGISTER]
    missing = [str(p) for p in paths if not p.is_file()]
    if missing:
        print(f"capabilities-skill: missing {', '.join(missing)}", file=sys.stderr)
        return 2
    caps = yaml.safe_load(paths[0].read_text())
    errors = cs.validate(caps, REPO)
    if errors:
        print("capabilities-skill: capabilities.yaml is invalid:\n  " + "\n  ".join(errors), file=sys.stderr)
        return 1
    return caps, yaml.safe_load(paths[1].read_text())


def _installed(caps, repos, install: bool) -> int:
    md, home = cs.skill_md(caps, repos), Path.home()
    if install:
        try:
            written = cs.install(md, home)
        except ValueError as e:
            print(f"capabilities-skill: {e}", file=sys.stderr)
            return 1
        print(f"capabilities-skill: installed ({len(written)} file(s) written); linked from "
              + ", ".join(f"~/{h}/skills" for h in cs.HARNESS_LINKS))
    problems = cs.installed_problems(md, home)
    if problems:
        print("capabilities-skill: installed skill is not current:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 1
    print("capabilities-skill: installed skill is current")
    return 0


def _register_block(caps, repos, write: bool) -> int:
    current = REGISTER.read_text()
    try:
        wanted = cs.splice(current, cs.block(caps, repos))
    except ValueError as e:
        print(f"capabilities-skill: {REGISTER.name}: {e}", file=sys.stderr)
        return 2
    if write:
        if wanted != current:
            REGISTER.write_text(wanted)
            print(f"capabilities-skill: rewrote the generated block in {REGISTER.name}")
        else:
            print("capabilities-skill: already in sync")
        return 0
    if wanted != current:
        print("capabilities-skill: STALE — the weyland-capabilities skill in register_bifrost_skills.py does not match "
              "capabilities.yaml + repos.yaml. Run: python3 scripts/capabilities-skill.py --write", file=sys.stderr)
        return 1
    print(f"capabilities-skill: in sync ({len(caps['capabilities'])} capabilities)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
