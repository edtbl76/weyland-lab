# Demo — Weyland capabilities discoverable from any managed repo (B241)

The `weyland-capabilities` skill makes an agent in any repository Weyland manages aware of what the lab offers it.
Operate: [runbooks/weyland-capabilities.md](../runbooks/weyland-capabilities.md).

## CLI walkthrough (RUN 2026-11-08)

**1. Generate and install** (the Bifrost copy and the user skill files):

[rogueone]
```bash
cd /home/edwardmangini/IdeaProjects/weyland && python3 scripts/capabilities-skill.py --write && python3 scripts/capabilities-skill.py --install
```

Seen: `rewrote the generated block in register_bifrost_skills.py`, `installed (1 file(s) written); linked from
~/.claude/skills, ~/.codex/skills`, `installed skill is current`. The links are relative
(`../../.agents/skills/weyland-capabilities`), like the existing user skills.

**2. The checks fail closed.**
- Before the first `--write`, `--check` printed `STALE … Run: python3 scripts/capabilities-skill.py --write` (exit 1).
- Before the first `--install`, `--check-installed` listed the missing file and both missing links (exit 1).
- After both: `in sync (15 capabilities)` and `installed skill is current` (exit 0).

**3. Claude Code picked it up live.** The running Claude Code session listed `weyland-capabilities` among its available
skills, with its description, as soon as the file was installed: no plugin, marketplace or restart.

**4. What an agent reads:** `python3 scripts/capabilities-skill.py --show`: first how to find the repo's name, then a
repo × lane table (10 active repos; CI on weyland-lab and stud.io only, the other lanes on all of them), then 15
capabilities, each with its scope, steps and runbook.

**5. The Bifrost marketplace serves again** (it was off from the v2 upgrade until now). The owner ran the
client-config registrar, then the skills registrar ([mcp-gateway.md](../runbooks/mcp-gateway.md) § Bifrost setup token):
- The first run wrote `skills_external_client_url` and then **failed its read-back**: Bifrost stores the string as
  `{"value": …, "type": "plain_text"}`. The script was fixed to read that shape (test built on the observed value).
- The re-run printed `unchanged: client_config already as owned`; the skills registrar printed
  `CREATED [meta] weyland-capabilities … 1 created, 0 updated, 26 unchanged, 0 failed`.
- Both marketplace routes went from 503 to 200; the catalog lists 592 plugins, including `bifrost-weyland-capabilities`.
- `claude plugin marketplace update bifrost-skills` and `codex plugin marketplace upgrade bifrost-skills` succeeded.
  The cached `bifrost-weyland-conventions` turned out identical to the served copy (that skill has not changed since
  August), so nothing had been missed.
- `--check-installed` still passes: the `weyland-capabilities` plugin is not installed beside the user file.

## Eyes-on (DONE 2026-11-08, owner confirmed)

1. Open a new terminal: `cd /home/edwardmangini/Documents/Studio/STUD.io && claude`.
2. Ask: "How do I get CI and a code scan for this repo?"
3. Confirm the agent loads `weyland-capabilities` without being told to and answers from it (Woodpecker for CI, the scan
   lane and SonarQube, the onboarding guide).
4. The same question in `codex` and `opencode` from the same folder (restart them first so they read skills). Owner
   confirmed both work, 2026-11-08.

## Cleanup

None. To uninstall: remove `~/.agents/skills/weyland-capabilities` and the two links.
