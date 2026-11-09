# Weyland capabilities skill — runbook

How a coding agent in **any repository Weyland manages** discovers what the lab offers it: the `weyland-capabilities`
Agent Skill, installed at user level on rogueone, so Claude Code, Codex and OpenCode load it in every repo without the
repo containing anything. Built by B241 (EMA-340, 2026-11-08). Demo: [demos/weyland-capabilities.md](../demos/weyland-capabilities.md).

## How it fits together

| Piece | Where | Role |
|---|---|---|
| Registry | `capabilities.yaml` (repo root) | the source: each capability, its scope, the steps an agent follows, its runbook |
| Per-repo coverage | `repos.yaml` `lanes` (CI, scan, PR, catalog, backup, IaC) and `linear_project` | who has which lane; never duplicated in the registry |
| Renderer | `scripts/lib/capabilities_skill.py`, CLI `scripts/capabilities-skill.py` | turns the two files into the skill |
| Installed skill | `~/.agents/skills/weyland-capabilities/SKILL.md`, linked from `~/.claude/skills/` and `~/.codex/skills/` | what the agents load (OpenCode also reads `~/.agents/skills` and `~/.claude/skills`) |
| Bifrost copy | the generated block in `services/weyland-dagster/scripts/register_bifrost_skills.py` | the same skill in Bifrost's Skills Repository and its plugin marketplace (published by the Dagster `bifrost_skills_registered` asset) |

Agents load the user skill files, not the marketplace plugin. The user file is regenerated from `repos.yaml` on every
change and reaches OpenCode, which has no plugin marketplace. Do not also install `bifrost-weyland-capabilities` from
the `bifrost-skills` marketplace: both would load. `--check-installed` reports that plugin as a duplicate.

## Change a capability

1. Edit `capabilities.yaml` (or `repos.yaml` for per-repo lanes). Every line must be true; a retired capability leaves
   the file in the same change.
2. Regenerate the Bifrost copy and reinstall the skill:

[rogueone]
```bash
cd /home/edwardmangini/IdeaProjects/weyland && python3 scripts/capabilities-skill.py --write && python3 scripts/capabilities-skill.py --install
```

Expected: `rewrote the generated block` (or `already in sync`), then `installed … linked from ~/.claude/skills,
~/.codex/skills` and `installed skill is current`.

3. Read what an agent will see: `python3 /home/edwardmangini/IdeaProjects/weyland/scripts/capabilities-skill.py --show`.

## Checks

- **CI** (repo-guards): `python3 scripts/capabilities-skill.py --check` fails when the Bifrost copy and the registry
  differ, or when the registry is invalid (unknown scope or lane, a runbook that does not exist, a duplicate key, no
  steps).
- **On rogueone**, after pulling a change someone else made:

[rogueone]
```bash
python3 /home/edwardmangini/IdeaProjects/weyland/scripts/capabilities-skill.py --check-installed
```

Expected: `installed skill is current`; exit 1 lists what is missing or stale (fix with `--install`).

## Does an agent find it?

Open a fresh session in a managed repo (for example `/home/edwardmangini/Documents/Studio/STUD.io`) and ask something
the skill answers, such as "how do I get CI and a code scan for this repo?". The agent should load
`weyland-capabilities` without being told to, and answer from it (the coverage table, then the steps). If it does
not, the skill's description (`DESCRIPTION` in `scripts/lib/capabilities_skill.py`) is what decides whether an agent
loads it: change it, regenerate and reinstall.

## Gotchas

- `--install` refuses to replace a real folder named `weyland-capabilities` in a harness's skills folder with a link;
  move it aside first.
- The skill is per user and per machine (rogueone). Another machine needs `--install` run there.
- Codex and OpenCode read their skills at start-up: restart an open session to see a change.
