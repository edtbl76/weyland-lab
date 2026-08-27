# Design records

**Design decision records** — the "why we built it this way" for the lab's systems. Moved here from the
**gitignored** `aidlc-docs/` on 2026-08-27, where 75 files sat untracked on a single disk while committed
documentation cited them as authoritative.

## Why this exists

`docs/backlog.md`, `docs/arch.md`, the runbooks and the demos all pointed at `aidlc-docs/*.md` as the
source of truth for how things were designed — B1's data mesh, B115's guardrails, B111's GPU serving,
B57a's image pipeline. Every one of those links was unresolvable for anyone who did not have that
machine's disk, and the directory was excluded by `.gitignore:102` (`/aidlc-docs/`). Same class of
problem as the live-only Port configuration that [B137] existed to fix — a system of record kept
somewhere it could not survive.

## What lives here vs `docs/concepts/`

| | Purpose | Audience |
|---|---|---|
| **`docs/design/`** (here) | **Design records** — decisions, alternatives weighed, specs, gotchas found while building | whoever changes the system next |
| **`docs/concepts/`** | **Concept pages** — what a thing is and how it fits, published to `docs.weyland.lab` | anyone reading the docs site |

Several subjects have both, deliberately: `guardrails-platform.md` (design) and
`concepts/guardrails.md` (published), `a2a-agent-roster.md` (the 24-agent roster) and
`concepts/realm-of-agents.md` (the overview), `application-taxonomy.md` and
`concepts/application-catalog.md`. The design record is the longer, decision-oriented one.

## What deliberately did NOT move

The rest of `aidlc-docs/` is **Method workspace output**, not design records — process artifacts from
the retired Method workflow (superseded by AI-DLC v2 on 2026-08-20, see
[aidlc-v2-migration.md](aidlc-v2-migration.md)). It stays gitignored:

- `aidlc-state.method-archive.md` — archived state tracking
- `inception/` — requirements analysis, user stories, units, execution plans
- `construction/plans/`, `construction/build-and-test/` — per-stage plans and build instructions
- `construction/u1/`, `u2-dagster/`, `u3-dagster/`, `u4-tool-server/` — per-unit functional/NFR/infrastructure design trees
- `audit/` — audit shards
- `*-plan.md` — stage plans (the `*-design.md` siblings moved; the plans did not)

The live AI-DLC v2 workspace is `aidlc/spaces/default/`, which is unrelated to this directory.

## Note for the next docs-site build

`site-techdocs/` is committed, generated MkDocs output and still contains the old `aidlc-docs/…`
paths in its HTML. Those correct themselves on the next site rebuild; do not hand-edit them.
