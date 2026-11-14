# Record architecture decisions as MADR files in docs/adr

## Status

accepted

Date: 2026-11-13

## Context and Problem Statement

The lab's decisions lived in 18 design records under `docs/design/`, verdict tables in `docs/concepts/`, Decision Record sections inside runbooks and prose in `docs/backlog.md`. `AGENTS.md` tells every agent to check them before proposing anything, but nothing listed them, numbered them, or said when one was superseded. How should the lab record decisions?

## Decision Drivers

* Every agent harness (Claude Code, Codex, OpenCode, Cline, Pi) must be able to read and add a decision.
* The RAG corpus, the docs site, the shared memory and the CI guards read files from the repo.
* The owner handles all git: a decision must not need an extra push step to exist.
* $0 and self-hosted.

## Considered Options

* `adr` Claude Code plugin (zircote-plugins/adr v0.2.0): MADR files in `docs/adr/`
* `git-adr` (zircote/git-adr v1.0.0): Markdown ADRs in git notes, exported to files
* Keep today's design records and concept verdicts, unindexed

## Decision Outcome

Chosen option: `adr` plugin, because it was the only option that kept every record in the B248 trial and needs no extra git step.

### Consequences

* Good, because ADRs are ordinary tracked files: they ride the owner's normal commit, and every reader already handles them.
* Good, because `scripts/check-adr.sh` (CI repo-guards) checks every ADR the same way whichever tool wrote it.
* Bad, because the plugin's commands (`/adr:new`, `/adr:supersede`) run in Claude Code only; other harnesses copy the template by hand (`docs/runbooks/adr.md`).
* Neutral: the design records stay where they are; an ADR links its design record instead of copying it.

## More Information

The B248 trial (2026-11-13), both tools on the same decision in a throwaway clone. `git-adr` attaches each ADR as a git note on `HEAD`, and git allows one note per commit: two ADRs created with no commit between them left only the second (both runs printed "Created"; reproduced in a 3-commit repo), and `supersede` printed "ADR not found" and lost the superseded ADR. It also ignored the status in the body, needs `git adr init` in every clone (fresh clones and CI see no notes), and every change needs a separate `git adr sync --push`. Its AI drafting and wiki sync are not implemented in 1.0. The plugin is installed from a pinned local clone (`~/.claude/plugin-sources/adr`, v0.2.0, `adr@local`) because upstream publishes no marketplace; its git integration is disabled (`.claude/adr.local.md`), so it never commits. Backlog B248, Linear EMA-348.
