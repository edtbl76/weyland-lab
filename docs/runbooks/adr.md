# Architecture Decision Records — runbook

The lab's decision log is [`docs/adr/`](../adr/README.md) (B248, [ADR-0001](../adr/0001-record-architecture-decisions-as-madr-files.md)).
Each decision has its own MADR file, `NNNN-slug.md`. Check the log before you propose anything: re-proposing a rejected option
wastes the owner's time (`AGENTS.md`).

There are two ways to write an ADR, and both produce the same file:
- **In Claude Code:** use the `adr` plugin (zircote-plugins/adr v0.2.0, installed as `adr@local`).
- **In any other harness** (Codex, OpenCode, Cline, Pi): copy the template by hand.

`scripts/check-adr.sh` checks every ADR the same way, whichever path wrote it.

## Rules every ADR follows

- Required sections (the guard fails without them): `## Status`, `## Context and Problem Statement`,
  `## Considered Options` (the alternatives, which is the inception rule's "Alternatives Rejected"), `## Decision Outcome`,
  and `### Consequences`. `## Decision Drivers` and `## More Information` are encouraged.
- Status: one of `proposed`, `accepted`, `deprecated` or `rejected`, or `Superseded by [ADR-NNNN](./NNNN-slug.md)`.
  Put a `Date: YYYY-MM-DD` line under it.
- **Link, don't copy.** If the decision came from a design record, a concept verdict or a runbook, link it under
  `## More Information`. The ADR is the index entry and the reasoning; the long analysis stays where it is.
- Numbers run `0001` upward with no gap. Every file has a row in [`docs/adr/README.md`](../adr/README.md).
- **Git is the owner's.** The plugin's git integration is off (`.claude/adr.local.md`), so it never commits. Hand over
  the changed files.

## New ADR

**Claude Code:**

```
/adr:new "Title of the decision"
```

It reads `.claude/adr.local.md`, takes the next number, asks for the context, the options and the drivers, writes
`docs/adr/NNNN-slug.md` from the MADR template (status `proposed`), and adds the index row.

**Any other harness:** copy the newest ADR as a starting point (it is already in the house shape), renumber it, rewrite
it, and add its row to the index:

[rogueone]
```
ls /home/edwardmangini/IdeaProjects/weyland/docs/adr/ | grep -E '^[0-9]{4}-' | tail -1
```

Then edit the copy, set `## Status` to `proposed` or `accepted`, and add `| [NNNN](./NNNN-slug.md) | Title | status | date |`
to the index table.

## List

[rogueone]
```
grep -E '^\| \[[0-9]{4}\]' /home/edwardmangini/IdeaProjects/weyland/docs/adr/README.md
```

(In Claude Code: `/adr:list`, or `/adr:list --status=accepted`.)

## Supersede

**Claude Code:**

```
/adr:supersede ADR-NNNN "Title of the new decision"
```

It creates the new ADR with `Supersedes [ADR-NNNN](...)` under its status, sets the old ADR's status to
`Superseded by [ADR-MMMM](...)`, and updates both index rows.

**By hand:** do the same three edits. Never delete or renumber the old ADR: a superseded decision is history, and the
guard checks that the `Superseded by` link resolves.

## Search

[rogueone]
```
grep -ril "keda" /home/edwardmangini/IdeaProjects/weyland/docs/adr/
```

(In Claude Code: `/adr:search "keda"`.) The log is also in the RAG corpus (it lives under `docs/`), so
`/context/search` finds it.

## Validate

[rogueone]
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/check-adr.sh
```

The exit code means:
- **0:** the log is valid.
- **1:** something is wrong, and every defect is named (a missing section, a bad status, a dangling `Superseded by`,
  a numbering gap or duplicate, or an index row out of step).
- **2:** the guard could not run (there is no `docs/adr/`, or no ADRs in it). This is never treated as a pass.

CI runs it in `repo-guards`.

## Reinstall the plugin

Upstream publishes no marketplace, so the plugin is installed from a pinned clone and a one-entry local marketplace.
To recreate it on a fresh machine:

[rogueone]
```
git clone -q --depth 1 --branch v0.2.0 https://github.com/zircote-plugins/adr.git /home/edwardmangini/.claude/plugin-sources/adr
```

Then write `/home/edwardmangini/.claude/plugin-sources/.claude-plugin/marketplace.json` (name `local`, a single plugin
`adr` with source `./adr`), and run:

[rogueone]
```
claude plugin marketplace add /home/edwardmangini/.claude/plugin-sources && claude plugin install adr@local
```

The plugin loads when a session starts. To move to a newer version, re-clone at the new tag after reading its changelog.
It has no hooks and no executables, but its commands can commit when git is enabled: keep `git.enabled: false`.

## Why not `git-adr`

It stores ADRs as git notes, and the B248 trial lost records with it: a second ADR silently overwrote the first, and a
supersede deleted the old one. The evidence is in [ADR-0001](../adr/0001-record-architecture-decisions-as-madr-files.md).
