# Architecture Decision Records — runbook

The lab's decision log is [`docs/adr/`](../adr/README.md) (B248, [ADR-0001](../adr/0001-record-architecture-decisions-as-madr-files.md)).
Each decision has its own MADR file, `NNNN-slug.md`. Check the log before you propose anything: re-proposing a rejected option
wastes the owner's time (`AGENTS.md`).

There are two ways to write an ADR, and both produce the same file:
- **In Claude Code:** use the `adr` plugin (zircote-plugins/adr v0.2.0, installed as `adr@local`).
- **In any other harness** (Codex, OpenCode, Cline, Pi): copy the template by hand.

`scripts/check-adr.sh` checks every ADR the same way, whichever path wrote it.

## When to write one

The same three cases as `AGENTS.md` (B250, 2026-11-19; `check-adr.sh` fails if the two lists differ).
**A decision gets an ADR when:**
- (a) a spike or investigation reaches an ADOPT or DON'T ADOPT verdict;
- (b) we choose between two or more options for a tool, component or pattern that would be costly to reverse;
- (c) an existing ADR is reversed: supersede it, never edit it in place.

What enforces each:
- **(a)** `check-adr.sh` fails when a `docs/backlog.md` item closed after 2026-11-13 carries a verdict and no ADR names
  its B-number (§ Validate). In Claude Code a hook also reminds the agent the moment it writes the verdict (§ The
  verdict reminder hook).
- **(b)** a judgment call no tool can detect: the rule above is what holds it. A spike's closing note names its ADR
  (the issue DoD).
- **(c)** `/adr:supersede` (§ Supersede); the guard checks every `Superseded by` link.

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

**Every new ADR, either path (B250):**
- Name the decision's backlog item (`B###`) under `## More Information`: that is the link `check-adr.sh` looks for.
- Add the ADR to the list in the shared-memory note `adr-log-b248` (`/home/edwardmangini/agent-memory/weyland/adr-log-b248.md`),
  one line: number, title, the verdict in a few words. Lab Recall answers "what did we decide about X?" from that
  list, and CI cannot see the memory store, so this step is the DoD's, not a guard's.

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
  a numbering gap or duplicate, an index row out of step, a verdict with no ADR, or a trigger list that differs
  between `AGENTS.md` and this runbook).
- **2:** the guard could not run (there is no `docs/adr/`, no ADRs in it, or no backlog). This is never treated as a pass.

**The missing-ADR check (B250).** Every `docs/backlog.md` item closed after 2026-11-13 whose `DONE <date> — …` status
carries a verdict must be named, by its B-number, under some ADR's `## More Information`. The verdict words are ADOPT /
adopted, DON'T ADOPT, WON'T DO, rejected and KEPT, in any case, and only inside the DONE status: "we rejected two
designs" in a paragraph does not count. They live in one place, `scripts/lib/adr_verdicts.py`, which the reminder hook
below imports too. Items closed before 2026-11-13 are exempt (B248 seeded the log from them). Every run prints
`adr: backlog: N closed since 2026-11-13, M with a verdict, K of them named by an ADR`, so a pattern that stopped
matching the backlog's wording shows as `0 with a verdict` instead of passing silently.
A concept doc's verdict (`docs/concepts/*`) is covered through the backlog item of the spike that produced it: the
concept tables carry no date, and CI's shallow clone has no history to date them by.

CI runs it in `repo-guards`.

## The verdict reminder hook

In Claude Code, `.claude/hooks/adr-verdict-reminder.py` (a `PostToolUse` hook on `Edit|MultiEdit|Write`, wired in
`.claude/settings.json`) watches `docs/backlog.md` and `docs/concepts/*.md`. When an edit **adds** a verdict, it hands
the agent a reminder: this is a decision, write the ADR (`/adr:new`, or `/adr:supersede` for a reversal), name the
item, update the memory note. It only reminds: it never blocks, calls no model and starts no agent.

- **What counts:** the verdict count after the edit is higher than before. For Edit and MultiEdit, `new_string`
  against `old_string`; for Write, the new content against the git `HEAD` copy. Fixing a typo in an item that already
  has its verdict stays silent. Any other file returns at once.
- **What it misses:** edits made through Bash (`python3`, `sed`) never reach a tool hook. The CI guard above catches
  those; the hook only reminds sooner. Every failure (bad input, no git) is silent, for the same reason.
- **Tests:** `scripts/tests/adr-verdict-reminder.bats` (hook-input JSON fixtures, plus a check that `settings.json`
  wires it). Proven live 2026-11-19: an Edit adding `DONE 2026-11-20 — DON'T ADOPT` to the backlog showed the
  reminder in the session, and `check-adr.sh` failed on the same line until it was removed.
- **AI-DLC reinstall:** `.claude/settings.json` also wires the AI-DLC engine's hooks. `/aidlc --doctor` only reads it,
  but its fix for a damaged file is to copy the engine's own `settings.json`, which has no entry for this hook. If
  that happens, re-add the entry (the bats wiring test fails until you do):

```
{ "matcher": "Edit|MultiEdit|Write", "hooks": [ { "type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/adr-verdict-reminder.py\"" } ] }
```

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
