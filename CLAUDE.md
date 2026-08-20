# weyland — homelab AI/data platform

Solo, $0, LAN-only homelab. This project uses **AI-DLC v2** for structured development.

## AI-DLC workflow
@AGENTS.md

Run `/aidlc` (scope auto-detected) to start/resume; `/aidlc --doctor` to validate;
`/aidlc --status` for progress. Stages/scopes live in `.claude/`; workspace is `aidlc/spaces/default/`.

## Project conventions (the quality bar the workflow serves)
- **Definition of Done** — the 7-pillar gate in `docs/definition-of-done.md`; nothing is "done" until it passes.
- **Backlog** = `docs/backlog.md` (ordered source of truth, B-numbered); **Linear** (emangini/EMA) = status.
- **Docs** — arch/hosts/api/schedules/runbooks/demos/diagrams under `docs/`; keep current on every change.
- **Knowledge libraries** — `knowledge-repos/` (engineering-knowledge · consulting-tools · industry-vertical)
  feed Bifrost skills/prompts + the DataHub glossary (data, not workflow).

## Operating rules
Host topology, GitOps, and the lab's hard-won conventions live in the persistent memory index + `docs/`.
