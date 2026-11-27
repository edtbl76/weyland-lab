# Golden-path shared code: one source, synced copies, a guard

## Status

proposed

Date: 2026-11-26 (decided by the owner on 2026-11-25: "One source, synced copies"; B261)

## Context and Problem Statement

B163 deepens every golden path to one deep contract (v2), with an integration tier per language ecosystem
([concepts/golden-path-capabilities.md](../concepts/golden-path-capabilities.md)). The paths of one language share
code that is framework-neutral: the `ItemStore` and its in-memory default, the Postgres, Valkey, Redpanda and MinIO
adapters, their integration tests, and the v2 smoke sequence. But each golden path must stay self-contained:
`golden-path-smoke` builds each image with only that path's directory as the build context, and `scripts/new-service.sh`
copies only that directory into a new service. How should four (and later 38) paths share code without breaking that?

## Decision Drivers

* A path builds, tests and scaffolds from its own directory, with no sibling reference.
* One source of truth: a fix lands once, not four (later ten ecosystems) times.
* Drift must fail CI, not be found later.
* A scaffolded service owns its code outright.

## Considered Options

* **One source, synced copies, a guard:** the source lives once in `golden-paths-shared/<lang>/`; a sync tool copies it
  into every path that opts in, each copy stamped as generated; `--check` (a repo guard) fails on drift.
* **One shared directory, the tooling taught to reach it:** no copies, but the image builds (a wider build context),
  `new-service.sh` and the lanes (an import path) all change, and every path depends on a sibling directory.
* **Independent copies per path:** simplest, but nothing stops them drifting apart.

## Decision Outcome

Chosen option: **one source, synced copies, a guard** (owner, 2026-11-25: "One source, synced copies").

* The source is `golden-paths-shared/<lang>/` (top level, so no tool that enumerates `golden-paths/<lang>/<framework>`
  mistakes it for a path). A path opts in with an empty `.golden-shared` marker.
* `scripts/sync-golden-shared.sh` writes the copies, each headed `GENERATED from golden-paths-shared/... edit the
  source, not this copy`; `--check` runs in the `repo-guards` CI step: exit 1 on a drifted or missing copy (named), 2
  when shared code has no opted-in path. Tested by `scripts/tests/sync-golden-shared.bats`.
* `new-service.sh` drops the marker and rewrites the header ("this service owns it now"): a scaffold is outside the sync.
* The Python lane never discovers `golden-paths-shared/` as a project; the copies are tested through each path.

**Proved by B261** (2026-11-26): the four Python paths (FastAPI, Django, Flask, Litestar) share `items_store.py`,
`items_backends.py`, `v2_smoke.py` and the integration conftest and adapter tests; each path keeps only its framework
code and one test of its own HTTP API on Postgres. All four pass their units at 100%, their image smoke, and the
integration runner against real backends (6/6 each); a scaffold of each passes out of the box.

### Consequences

* Good, because a fix to the shared code is made once and the guard proves every copy carries it.
* Good, because every path stays buildable and scaffoldable from its own directory, exactly as before.
* Bad, because the repo holds N copies of the shared files (small: ~300 lines per Python path), and an edit made to a
  copy instead of the source fails CI until it is moved to the source.
* Neutral: the same pattern serves B262-B268 (one source per language ecosystem).

**Revisit when:** the build or scaffold tooling can reach a shared directory without widening every path's context.

## More Information

* Design: [docs/concepts/golden-path-capabilities.md](../concepts/golden-path-capabilities.md); runbook:
  [docs/design/golden-paths.md](../design/golden-paths.md). Backlog: B261 (Linear EMA-364), parent B163 (EMA-220).
