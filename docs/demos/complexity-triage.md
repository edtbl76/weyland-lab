# Demo — complexity triage (B162)

**RUN 2026-09-21.** The lab's machine-checkable reading of complexity: length nominates, structure and the
codebase-relative outlier decide, the inverse smell is caught in the other direction. Advisory, adjustable.

- Engine: `scripts/lib/complexity_triage.py` · lane: `scripts/check-complexity.sh` · knobs:
  `scripts/complexity-triage.json`
- Concept: [concepts/reading-complexity.md](../concepts/reading-complexity.md) · runbook:
  [runbooks/complexity-triage.md](../runbooks/complexity-triage.md) · diagram:
  [diagrams/flow-complexity-triage.md](../diagrams/flow-complexity-triage.md)

## The run

```
bash scripts/check-complexity.sh
```

First pass over the real-code services (weyland-dagster, weyland-guard, weyland-tool-server, scripts, the Flink
Java): **20 TANGLED · 2 SHALLOW · 11 OUTLIER-REVIEW · 2 DEEP.** The reading proved out on real code:

- **Deep vs tangled separated correctly.** `_build_vectors` (ccn 35, density 0.42) and `emit_mesh_glossary`
  (ccn 33, 0.41) → `TANGLED`; a raw-length rule would have lumped them with the clean store-writers.
- **True nesting earned its place.** `neo4j_write` (ccn 9, density **0.08** — reads as deep) is `TANGLED`
  because it hid a **6-level pyramid** — the case density alone misses.
- **The inverse detector caught real over-split:** `finance_common.py` / `music_common.py` / `health_common.py`
  each re-declared the same `client()` and `download()` pass-throughs.
- **Self-calibrating stage 3:** z_loc up to 6.7 on `neo4j_write`, because this codebase's mean function is small.
- **Honesty check:** the tool flagged its own `_numeric_verdict` (a dense classifier) — and it now passes its
  own triage after refactoring.

## Eyes-on: the remediation, verified

Nineteen of the 20 TANGLED were refactored to deep modules and both SHALLOW findings fixed; one TANGLED was
adjudicated acceptable (`build_store_load_assets` — a low-density per-store registry). Zero behavior change,
verified at every step:

- `datahub_emit.py` (7 fns) — **138 tests green** (`test_datahub_emit.py` + `test_loaders.py`) after each
- `loaders.py` (2 fns) — **37 tests green** (`test_loaders.py`)
- `extract_epub` — **7 tests green** (`test_kindle_text_parse.py`)
- `_numeric_verdict`/`_numeric_findings` — **8 tests green** (`test_complexity_triage.py`); the tool clean on
  itself
- `cmd_merge` — **machine-inventory.bats green**
- store writers + other assets (untested integration code) — compile + triage-clear + pure code-motion

Re-run after remediation: **1 TANGLED (the adjudicated one) · 0 SHALLOW · 8 OUTLIER-REVIEW · 2 DEEP** — the
codebase now sits exactly where the triage prescribes (the residual OUTLIER/DEEP are the "human-glance / keep"
categories, not stop-and-fix).

## Toolchain-verified (the way CI runs it)

- Engine tests: `pytest test_complexity_triage.py` **8/8** in a clean `python:3.12-slim` with deps installed
  fresh from `scripts/requirements-test.txt`.
- Wrapper tests: `bats scripts/tests/complexity.bats` **7/7** in `bats/bats:latest`.
- The `--gate` posture proven: a stubbed `TANGLED`/`SHALLOW` finding exits 1; a clean run exits 0; a failing
  engine exits 2 (fail-closed).

## Teardown

N/A — repo tooling. The engine + lane stay as the standing advisory check; no cluster workload, nothing to tear
down.
