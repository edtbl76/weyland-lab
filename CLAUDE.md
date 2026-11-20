# weyland — Claude Code

Project-wide instructions are harness-neutral and live in `AGENTS.md` (read by every harness):

@AGENTS.md

## Claude Code specifics
- **AI-DLC v2:** run `/aidlc` (scope auto-detected) to start/resume; `/aidlc --doctor` to validate; `/aidlc --status`
  for progress. Stages/scopes live in `.claude/`; workspace is `aidlc/spaces/default/`.
- **Memory:** Claude Code's auto-memory (the directory named in `AGENTS.md` § Agent memory) is native here — write
  durable lessons there. A rule that EVERY harness must follow goes in `AGENTS.md`, not only in memory.

# Compact instructions

Sessions here run long and compact many times (B255, 2026-11-20), so the summary is the only memory of what came before.
Recall first, then brevity. Always keep:
- **The active item and its state:** its B-number and Linear id, what is done and verified, what is pushed or shipped,
  what is pending and on whom (the owner or the agent), and the exact next step.
- **Decisions and approvals:** each owner decision in their own words, with what it approved; anything not approved is
  marked not approved. Never record an issue as closable without the owner's approval and a DoD table.
- **Instructions given only in conversation** (not yet in `AGENTS.md` or a memory note), verbatim.
- **Identifiers in use:** commit SHAs, image tags, pipeline numbers, file paths, commands handed to the owner, and
  background tasks still running.
- **Open threads and caveats:** failures not yet fixed, numbers not yet verified, questions waiting on the owner.
Drop: raw tool output, file dumps, and logs once their conclusion is recorded.
