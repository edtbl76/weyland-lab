# Adopt Herdr for interactive multi-agent work, alongside Emdash

## Status

accepted

Date: 2026-11-23 (owner: "accept the ADR")

## Context and Problem Statement

The lab runs several coding-agent harnesses on rogueone (Claude Code, Codex, OpenCode, Cline, Pi; `AGENTS.md` is
harness-neutral) and Emdash's unattended conveyor ([ADR-0006](./0006-vibe-kanban-is-out.md), B179). There is no single
place to see which interactive agent is working, blocked on a question or idle, and only Claude Code keeps its
sessions alive without a terminal. Herdr (v0.9.5, Apache-2.0) is a terminal runtime that claims both. B257 evaluated it
from its source and docs, installed a pinned release, and ran a trial on rogueone with Claude Code and Codex in parallel
on real lab tasks.

## Decision Drivers

* The owner, 2026-11-23: "At some point, I will likely have multiple agents. This is a viable capability."
* Nothing that phones home by default may run unchecked (the reason Vibe Kanban was rejected, ADR-0006).
* $0, pinned installs with verified checksums, everything host-installed is inventoried.
* Do not replace or duplicate Emdash's conveyor without its own decision.

## Considered Options

* Adopt Herdr for interactive multi-agent work, alongside Emdash.
* Reject it: Claude Code's own background sessions plus Emdash cover today's single-session work.
* Defer until parallel multi-harness work is routine.

## Decision Outcome

Chosen option: **adopt alongside Emdash for interactive multi-agent work** (owner, 2026-11-23, above). The trial found:

* **Persistence:** a real attached client killed with SIGHUP (an SSH drop) or SIGKILL left both agents running with
  the same process IDs. A server or machine restart ends them (documented).
* **State:** Claude Code's and Codex's approval prompts showed `blocked` within 4 seconds and `working`/`idle` tracked
  a parallel run; but an unfamiliar Codex start-up question showed `idle`.
* **Hand-off:** `herdr agent prompt <agent> --wait` handed Codex a task from inside Herdr and returned its correct
  answer. An agent doing this itself needs permission to run `herdr`.
* **Network:** by default 24 HTTPS GETs to herdr.dev at start-up and every 30 minutes, including detection-rule updates
  applied automatically. With both checks off: zero connections in 36 minutes, against a control that made 48
  requests. The lab keeps the version check on (owner, 2026-11-23: "yes, turn the version check on"; one GET of
  `latest.json`, verified) so a new release is noticed, and the rule updates off.
* **Cost:** about 20 MB of memory per server, negligible CPU.

Emdash keeps the unattended conveyor; Herdr does not see its runs.

### Consequences

* Good, because several harnesses can run side by side with one view of which needs an answer, and they survive a
  dropped connection.
* Good, because the hand-off API is a concrete input for B256 (shared context for many agents).
* Bad, because `idle` can hide an unfamiliar prompt; the runbook says to read a pane before typing into it.
* Bad, because detection rules are frozen at the pinned version (remote updates off): upgrades are by hand, with the
  network check re-run each time; Herdr's own version check announces a new release.
* Neutral: the machine inventory gained a `binary` kind to catalog it (Closing Gaps: 28 binaries in `~/.local/bin`
  were invisible), and Port's `installed_package` blueprint accepts it.

**Revisit when:** a Herdr release changes its network behaviour or the `[update]` keys, Emdash gains a live view of
interactive agents, or B256 designs its own hand-off channel.

## More Information

* Evaluation, trial and network check: [docs/concepts/herdr-evaluation.md](../concepts/herdr-evaluation.md).
* Runbook: [docs/runbooks/herdr.md](../runbooks/herdr.md). Multi-harness: [docs/concepts/multi-harness.md](../concepts/multi-harness.md).
* Backlog B257 (Linear EMA-358). Related: [ADR-0006](./0006-vibe-kanban-is-out.md) (Emdash), B256 (EMA-357).
