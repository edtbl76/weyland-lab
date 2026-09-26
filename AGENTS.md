# weyland — homelab AI/data platform (instructions for every agent harness)

Solo, $0, LAN-only homelab run by one person (Edward). This file is **harness-neutral**: Claude Code, Codex, OpenCode,
Cline and Pi all read it (Claude Code via `CLAUDE.md`, which imports it). Put project-wide rules HERE, not in a
harness-specific file, so every agent gets them. See `docs/concepts/multi-harness.md`.

## Project conventions (the quality bar)
- **Definition of Done** — the 9-pillar gate in `docs/definition-of-done.md`; nothing is "done" until it passes.
  Pillar 9 is disaster recovery: every stateful system has a row in `docs/dr.md` with a tested restore.
- **Closing Gaps** — the owner's term for the prework an issue needs because doing it exposed a gap in the wider
  estate (e.g. B194 had no DR catalog to add a Linear backup to, so `docs/dr.md` came first). When the owner says
  "Closing Gaps", or you find one: close the gap BEFORE the issue's own work, and ask three questions — does a
  **DoD gate** need adding or tightening, what **documentation** must now exist, and what **audit** (a guard, a
  drill, a sweep) keeps the gap closed? Record the gap in the issue and the backlog so it isn't lost.
- **Backlog** = `docs/backlog.md` (ordered source of truth, B-numbered); **Linear** (workspace emangini, team EMA) =
  status. A new backlog item gets a Linear issue in the same change; `scripts/check-linear-sync.sh` must exit 0.
- **Every issue an agent drafts is implementation-ready** — beyond Why/Scope it carries **Technical context** (the
  affected systems, files, services, APIs — host, path, role), **Acceptance criteria** (testable pass/fail checks),
  **Edge cases & failure modes**, and **Out of scope** (the Linear issue templates hold these sections).
  A Why + Scope issue is not done being written: SpecBot scored one 51/100 on exactly these gaps (EMA-240, 2026-09-25). Check with `@SpecBot` in the issue before delegating (threshold 80).
- **Docs** — arch/hosts/api/schedules/runbooks/demos/diagrams under `docs/`; keep them current on every change.
  Architecture model: `docs/architecture/weyland.likec4`. Design records: `docs/design/`; concepts: `docs/concepts/`.
- **Knowledge libraries** — `knowledge-repos/` feed Bifrost skills/prompts + the DataHub glossary (data, not workflow).
- **Decisions already made** live in `docs/backlog.md`, `docs/concepts/*` verdict tables and the runbooks. **Check them
  before proposing anything** — re-proposing a rejected option (e.g. KEDA, Cyrus) wastes the owner's time.

## Operational just-dos (do these without asking; don't improvise a substitute)
- **Every operational task has ONE canonical command — it lives in a `docs/runbooks/*.md`.** Find it and use it
  verbatim. Never hand-roll a substitute (a raw `curl`, an ad-hoc `kubectl`). If no runbook command exists, that is
  the gap — add it to the runbook.
- **Trigger CI actively; never wait for a cron:** `woodpecker-cli pipeline create edtbl76/weyland-lab --branch main`
  (creds from `scripts/.env`; see `docs/runbooks/woodpecker.md`).
- **Prove new/changed code in its Docker toolchain image BEFORE the push** — CI confirms, it does not discover.
- **Run the FULL local guard suite before any handoff** (the `repo-guards` step in `.woodpecker.yml`), not one guard —
  the first failure masks later ones.
- **Fail closed:** an absent, empty, or errored result is NEVER success. Read a tool's OUTPUT, not just its exit code.
- **Ship image bumps with `scripts/ship-images.sh`**, never a hand merge.

## Hard rules (apply to every harness)
- **The owner handles ALL git** — never commit, push, or open/merge PRs unless explicitly asked.
- **Secrets never pass through chat or output.** Read them from the gitignored `scripts/.env`
  (`set -a && . scripts/.env && set +a`); never ask the owner to paste a token; never `echo`/`printf` a secret value.
- **Cluster is read-only for agents** except a write the owner explicitly authorized. Changes go through git → Argo CD
  (every app runs `selfHeal: true`, so live edits and `kubectl rollout undo` are silently reverted).
- **Docker verification runs as the invoking user** (`--user "$(id -u):$(id -g)"`) or with `:ro` mounts — a root
  container writing into the repo breaks git for the owner.
- **Commands handed to the owner:** absolute paths only (never relative), one step, the host label (`[rogueone]`,
  `[mother]`) on its own line OUTSIDE the code fence. The agent session runs on **rogueone**; `kubectl` runs on mother.
- **$0 budget.** Free tiers or self-hosted; cloud is fine only if genuinely free (not a trial).
- **Ask before changing** anything non-trivial: propose, get a yes, then build. Ask one question at a time; lead with a
  recommendation, not a menu. Don't create records (issues, docs) you won't complete.
- **No emojis** in anything written for the owner or the repo.

## Agent memory
Durable lessons and decisions currently live in Claude Code's auto-memory:
`/home/edwardmangini/.claude/projects/-home-edwardmangini-IdeaProjects-weyland/memory/` — `MEMORY.md` is the index,
one Markdown note per fact. **Other harnesses on rogueone: read `MEMORY.md` and the notes it links before proposing
work (read-only — do not edit them).** A shared, harness-neutral memory store is planned (B182,
`docs/design/shared-agent-memory-design.md`); until it exists, a rule every harness must follow belongs in THIS file.

## AI-DLC
Structured development uses **AI-DLC v2**, installed for **Claude Code only** (`.claude/`, invoked with `/aidlc`;
workspace `aidlc/spaces/default/`; rule layers in `aidlc/spaces/default/memory/`). Runbook:
`docs/runbooks/aidlc-workflow.md`. Other harnesses follow the conventions above but do not run the `/aidlc` engine.
