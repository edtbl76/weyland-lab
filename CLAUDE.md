# weyland — Claude Code

Project-wide instructions are harness-neutral and live in `AGENTS.md` (read by every harness):

@AGENTS.md

## Claude Code specifics
- **AI-DLC v2:** run `/aidlc` (scope auto-detected) to start/resume; `/aidlc --doctor` to validate; `/aidlc --status`
  for progress. Stages/scopes live in `.claude/`; workspace is `aidlc/spaces/default/`.
- **Memory:** Claude Code's auto-memory (the directory named in `AGENTS.md` § Agent memory) is native here — write
  durable lessons there. A rule that EVERY harness must follow goes in `AGENTS.md`, not only in memory.
