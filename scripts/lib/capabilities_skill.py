"""Render capabilities.yaml + repos.yaml into the `weyland-capabilities` Agent Skill (B241). Stdlib only.

The skill body tells the coding agent in ANY managed repository what Weyland offers it, how to use each capability,
and which repos already have which lane. Per-repo coverage for a `scope: lane` capability comes from repos.yaml
`lanes`, never from this registry. `block()` is the Python source spliced into register_bifrost_skills.py between
BEGIN/END markers (that script runs in a pod over stdin, so it cannot read files; the skill text must live in it).
"""
from __future__ import annotations

import json
from pathlib import Path

NAME = "weyland-capabilities"
CATEGORY = "meta"
LANES = [("ci", "CI"), ("scan", "Scan"), ("pr", "PR"), ("catalog", "Catalog"), ("backup", "Backup"), ("iac", "IaC")]
SCOPES = {"lane", "all", "weyland"}
BEGIN = "# BEGIN GENERATED weyland-capabilities (scripts/capabilities-skill.py --write; do not edit by hand)"
END = "# END GENERATED weyland-capabilities"
DESCRIPTION = (
    "What the weyland lab offers the repositories it manages (CI on Woodpecker, code scanning and SonarQube, the "
    "Linear project and issue tracking, PR lifecycle, Port catalog, backups, GitHub-as-code, Bifrost MCP tools, shared "
    "agent memory, golden-path templates) and how to use each from inside one of those repos. Load it when working in "
    "any managed repository and the task touches CI, tests, scanning, issues, deploys, onboarding or lab tooling."
)


def _active(repos: dict) -> list[dict]:
    return [r for r in repos.get("repos", []) if r.get("status") == "active"]


def _scope_errors(key: str, c: dict) -> list[str]:
    scope = c.get("scope")
    if scope not in SCOPES:
        return [f"{key}: unknown scope {scope!r} (lane | all | weyland)"]
    if scope != "lane":
        return []
    lane_keys = {k for k, _ in LANES}
    if not c.get("lane"):
        return [f"{key}: scope lane needs a lane"]
    if c["lane"] not in lane_keys:
        return [f"{key}: unknown lane {c['lane']!r} (one of {', '.join(sorted(lane_keys))})"]
    return []


def _capability_errors(c: dict, root: Path) -> list[str]:
    key = c.get("key", "?")
    errors = _scope_errors(key, c)
    if not c.get("use"):
        errors.append(f"{key}: no use steps")
    rb = c.get("runbook")
    if not rb or not (root / "docs" / "runbooks" / rb).resolve().is_file():
        errors.append(f"{key}: runbook {rb!r} does not exist under docs/runbooks/")
    return errors


def validate(caps: dict, root: Path) -> list[str]:
    """Every problem in the registry, as readable strings (empty = valid)."""
    errors, seen = [], set()
    for c in caps.get("capabilities", []):
        key = c.get("key", "?")
        if key in seen:
            errors.append(f"{key}: duplicate key")
        seen.add(key)
        errors += _capability_errors(c, root)
    return errors


def _coverage_table(repos: dict) -> list[str]:
    head = "| Repository | Linear project | " + " | ".join(label for _, label in LANES) + " |"
    sep = "|---|---|" + "---|" * len(LANES)
    rows = [head, sep]
    for r in _active(repos):
        lanes = r.get("lanes") or {}
        cells = ["yes" if lanes.get(k) else "no" for k, _ in LANES]
        rows.append(f"| {r['name']} | {r.get('linear_project', '-')} | " + " | ".join(cells) + " |")
    return rows


def _scope_line(c: dict, repos: dict) -> str:
    if c["scope"] == "all":
        return "Every managed repository on rogueone has it; nothing to set up."
    if c["scope"] == "weyland":
        return "weyland-lab only today."
    have = [r["name"] for r in _active(repos) if (r.get("lanes") or {}).get(c["lane"])]
    return f"Repos with it now: {', '.join(have) or 'none'} (repos.yaml lane `{c['lane']}`)."


def render(caps: dict, repos: dict) -> str:
    lines = [
        "This repository is one of the repositories the **weyland lab** manages. Weyland offers it the capabilities "
        "below. Use them instead of inventing a parallel setup, and follow the lab's house rules (the "
        "`weyland-conventions` skill).",
        "",
        "**First, find this repo's name**: `basename \"$(git rev-parse --show-toplevel)\"` (it should match a name in "
        "`/home/edwardmangini/IdeaProjects/weyland/repos.yaml`). If it is not there, the repo is not managed yet: ask "
        "the owner before onboarding it.",
        "",
        "## Which repo has which lane",
        "",
        *_coverage_table(repos),
        "",
        "Lanes marked `no` can be added: run the onboarding guide (below) for the exact steps.",
        "",
        "## Capabilities",
    ]
    for c in caps.get("capabilities", []):
        summary = c["summary"][:1].upper() + c["summary"][1:]
        lines += ["", f"### {c['name']}", "", f"{summary}. {_scope_line(c, repos)}", ""]
        lines += [f"- {step}" for step in c["use"]]
        lines += ["", f"Runbook: `/home/edwardmangini/IdeaProjects/weyland/docs/runbooks/{c['runbook']}`"]
    lines += ["", "Generated from `capabilities.yaml` and `repos.yaml` in the weyland repo (B241). If something here "
              "is wrong, fix it there, not in this skill."]
    return "\n".join(lines) + "\n"


HARNESS_LINKS = (".claude", ".codex")   # each gets <home>/<harness>/skills/<NAME> -> ../../.agents/skills/<NAME>
SHARED = Path(".agents") / "skills" / NAME   # relative to the home directory
SKILL_FILE = "SKILL.md"


def skill_md(caps: dict, repos: dict) -> str:
    """The SKILL.md file: frontmatter (name, description) then the rendered body."""
    desc = DESCRIPTION.replace('"', '\\"')
    return f'---\nname: {NAME}\ndescription: "{desc}"\n---\n' + render(caps, repos)


def install(md: str, home: Path) -> list[Path]:
    """Write <home>/.agents/skills/<NAME>/SKILL.md (read by OpenCode and the cross-harness tools) and link it from each
    harness's own skills folder, relative, as the existing user skills are linked. Returns the files written (empty
    when nothing changed). Refuses to replace a real folder with a link."""
    shared = home / SHARED
    shared.mkdir(parents=True, exist_ok=True)
    target = shared / SKILL_FILE
    written = []
    if not target.is_file() or target.read_text() != md:
        target.write_text(md)
        written.append(target)
    for harness in HARNESS_LINKS:
        link = home / harness / "skills" / NAME
        rel = Path("..") / ".." / SHARED
        if link.is_symlink():
            if link.readlink() == rel:
                continue
            link.unlink()
        elif link.exists():
            raise ValueError(f"{link} exists and is not a symlink; refusing to replace it")
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(rel)
    return written


def installed_problems(md: str, home: Path) -> list[str]:
    """What is missing or stale in the installed skill (empty = installed and current)."""
    problems = []
    target = home / SHARED / SKILL_FILE
    if not target.is_file():
        problems.append(f"{target} is missing")
    elif target.read_text() != md:
        problems.append(f"{target} differs from capabilities.yaml + repos.yaml")
    for harness in HARNESS_LINKS:
        link = home / harness / "skills" / NAME
        if not (link.is_symlink() and (link / SKILL_FILE).is_file()):
            problems.append(f"{link} is not a working link to the shared skill")
    return problems + _plugin_duplicates(home)


PLUGIN_PREFIX = f"bifrost-{NAME}@"   # how Claude Code names the Bifrost marketplace's copy of this skill


def _plugin_duplicates(home: Path) -> list[str]:
    """The Bifrost marketplace serves this skill too; installed as a plugin it would load beside the user file."""
    registry = home / ".claude" / "plugins" / "installed_plugins.json"
    if not registry.is_file():
        return []
    plugins = json.loads(registry.read_text()).get("plugins", {})
    return [f"duplicate: plugin {key} is installed beside the user skill; run: claude plugin uninstall {key}"
            for key in plugins if key.startswith(PLUGIN_PREFIX)]


def block(caps: dict, repos: dict) -> str:
    """Python source appending this skill to register_bifrost_skills.py's SKILLS list."""
    return f"SKILLS.append(({NAME!r}, {CATEGORY!r},\n    {DESCRIPTION!r},\n    {render(caps, repos)!r}))"


def splice(text: str, new_block: str) -> str:
    """Replace what is between the BEGIN/END markers. Missing markers is an error (fail closed)."""
    if text.count(BEGIN) != 1 or text.count(END) != 1 or text.index(BEGIN) > text.index(END):
        raise ValueError("register script must contain exactly one BEGIN and one END markers, in order")
    head, rest = text.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    return f"{head}{BEGIN}\n{new_block}\n{END}{tail}"
