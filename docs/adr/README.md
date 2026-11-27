# Architecture Decision Records

The lab's decision log (B248, ADR-0001). One MADR file per decision, numbered `NNNN-slug.md`. Check here before
proposing anything: re-proposing a rejected option wastes the owner's time (`AGENTS.md`).

How to add, supersede and search: [docs/runbooks/adr.md](../runbooks/adr.md). `scripts/check-adr.sh` (CI repo-guards)
checks every ADR's sections and status, the numbering, and this index.

## ADR Index

| ID | Title | Status | Date |
|----|-------|--------|------|
| [0001](./0001-record-architecture-decisions-as-madr-files.md) | Record architecture decisions as MADR files in docs/adr | accepted | 2026-11-13 |
| [0002](./0002-ci-runs-on-woodpecker-never-github-actions.md) | CI runs on Woodpecker, never GitHub Actions | accepted | 2026-11-12 |
| [0003](./0003-retire-keda-commit-replicas-to-git.md) | Retire KEDA; scale data-mesh stores by committing replicas to git | accepted | 2026-08-22 |
| [0004](./0004-dont-adopt-linear-coding-agent-or-cyrus.md) | Don't adopt Linear's coding Agent or its self-hosted variants (Cyrus) | accepted | 2026-09-25 |
| [0005](./0005-dont-adopt-delta.md) | Don't adopt Delta (delta.dev) | accepted | 2026-10-29 |
| [0006](./0006-vibe-kanban-is-out.md) | Vibe Kanban is out | accepted | 2026-10-09 |
| [0007](./0007-reject-ragas-use-llm-as-judge.md) | Reject Ragas; generate and score evals with direct prompts and an LLM judge | accepted | 2026-06-12 |
| [0008](./0008-dont-adopt-icepanel-keep-likec4.md) | Don't adopt IcePanel; keep the architecture model in LikeC4 | accepted | 2026-11-03 |
| [0009](./0009-graph-traversal-does-not-beat-vector-search.md) | Graph-aware retrieval does not beat vector search on this corpus | accepted | 2026-11-12 |
| [0010](./0010-adaptive-retrieval-depth-for-comparisons.md) | Search comparison questions at twice the depth; retire the experimental retrieval modes | accepted | 2026-11-13 |
| [0011](./0011-dont-adopt-sentry-saas.md) | Don't adopt Sentry SaaS | accepted | 2026-11-13 |
| [0012](./0012-timberback-bare-metal-ubuntu-on-btrfs.md) | Run timberback as a bare-metal Ubuntu k3s worker on btrfs, not under Proxmox | accepted | 2026-11-14 |
| [0013](./0013-keep-mlflow-on-mother.md) | Keep MLflow on mother | accepted | 2026-11-17 |
| [0014](./0014-dont-adopt-bifrost-agent-gateway-or-relays.md) | Don't adopt Bifrost's Agent Gateway or Relays | superseded by [0015](./0015-adopt-bifrost-agent-gateway-for-the-realm.md) | 2026-11-19 |
| [0015](./0015-adopt-bifrost-agent-gateway-for-the-realm.md) | Adopt Bifrost's Agent Gateway for the Realm (Relays stay out) | accepted | 2026-11-19 |
| [0016](./0016-simplify-the-realm-on-the-free-lane.md) | Simplify the Realm of Agents on the free lane | accepted | 2026-11-20 |
| [0017](./0017-context-engineering-for-the-harness-and-services.md) | Context engineering for the coding-agent harness and the AI services | accepted | 2026-11-22 |
| [0018](./0018-adopt-herdr-for-interactive-multi-agent-work.md) | Adopt Herdr for interactive multi-agent work, alongside Emdash | accepted | 2026-11-23 |
| [0019](./0019-shared-context-layers-with-governed-writes.md) | Shared context for many humans and agents: layers in one store, with governed writes | accepted | 2026-11-24 |
| [0020](./0020-golden-path-shared-code-one-source-synced-copies.md) | Golden-path shared code: one source, synced copies, a guard | proposed | 2026-11-26 |

## Status Legend

| Status | Description |
|--------|-------------|
| proposed | Decision is under consideration |
| accepted | Decision has been approved and is active |
| deprecated | Decision is no longer recommended |
| superseded | Decision has been replaced by another ADR (`Superseded by [ADR-NNNN](...)`) |
| rejected | Decision was considered but not adopted |

## Numbering

These numbers are the lab-wide log. A design record may still number its own internal decisions (for example the
"ADR-1…7" inside [alert-to-linear-design.md](../design/alert-to-linear-design.md)); those are local to that document,
not entries here.
