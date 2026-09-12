# weyland — homelab AI/data platform

Solo, $0, LAN-only homelab. This project uses **AI-DLC v2** for structured development.

## AI-DLC workflow
@AGENTS.md

Run `/aidlc` (scope auto-detected) to start/resume; `/aidlc --doctor` to validate;
`/aidlc --status` for progress. Stages/scopes live in `.claude/`; workspace is `aidlc/spaces/default/`.

## Project conventions (the quality bar the workflow serves)
- **Definition of Done** — the 8-pillar gate in `docs/definition-of-done.md`; nothing is "done" until it passes.
- **Backlog** = `docs/backlog.md` (ordered source of truth, B-numbered); **Linear** (emangini/EMA) = status.
- **Docs** — arch/hosts/api/schedules/runbooks/demos/diagrams under `docs/`; keep current on every change.
- **Knowledge libraries** — `knowledge-repos/` (engineering-knowledge · consulting-tools · industry-vertical)
  feed Bifrost skills/prompts + the DataHub glossary (data, not workflow).

## Operating rules
Host topology, GitOps, and the lab's hard-won conventions live in the persistent memory index + `docs/`.

### Operational just-dos (do these without asking; don't improvise a substitute)
- **Every operational task has ONE canonical command — it lives in a `docs/runbooks/*.md`.** Before running or
  proposing any op, find that command and use it verbatim. Never hand-roll a substitute (a raw `curl`, an ad-hoc
  `kubectl`) when a script/runbook command exists. If you don't know the command, grep `docs/runbooks/` — don't guess.
- **Trigger CI actively; never wait for a cron.** Run it: `woodpecker-cli pipeline create edtbl76/weyland-lab --branch main`
  (creds from `scripts/.env`; watch with `woodpecker-cli pipeline ps edtbl76/weyland-lab <N>`). See `docs/runbooks/woodpecker.md`.
- **Prove new/changed code in its Docker toolchain image BEFORE the push** (test + selfcheck + build/serve) — CI confirms, it does not discover.
- **Run the FULL local guard suite before any ship/handoff**, not one guard — the first failure masks later ones.
- **Fail closed:** an absent, empty, or errored result is NEVER success; read a tool's OUTPUT, not just its exit code.
- **Ops commands go IN the runbook, not chat.** If an op has no runbook command, that's the gap — add it.
