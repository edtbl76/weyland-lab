# Runbook — complexity triage (B162)

How the lab reads complexity as a machine: `scripts/lib/complexity_triage.py` (engine),
`scripts/check-complexity.sh` (lane), `scripts/complexity-triage.json` (the adjustable knobs). The *why* is
[concepts/reading-complexity.md](../concepts/reading-complexity.md); this is the *how*.

## The canonical command

```
bash scripts/check-complexity.sh
```

Advisory — it prints the graded findings and exits 0. Default paths are the real-code services + `scripts`
(the Flink Java included). To gate (any `TANGLED`/`SHALLOW` → exit 1):

```
bash scripts/check-complexity.sh --gate
```

To scope it to specific paths, pass them after the flags:

```
bash scripts/check-complexity.sh nodes/mother/lab/weyland-platform/services/weyland-dagster/weyland_pipeline
```

## What it reports

Length only NOMINATES a function; the verdict comes from structure (cyclomatic density + true max-nesting) and
from how the function compares to the rest of THIS codebase (a self-calibrating z-score). Verdicts:

| Verdict | Meaning | Action |
|---|---|---|
| `TANGLED` | long AND dense / deeply-nested control flow | stop and fix |
| `SHALLOW` | pass-through / over-split delegation (the inverse smell) | stop and fix |
| `OUTLIER_REVIEW` | long AND unusual for this codebase, but not clearly tangled | a human glance |
| `DEEP` | long but a clean signature over sequential work | acceptable (silent unless `--show-deep`) |

## The adjustable knobs

Every threshold is in `scripts/complexity-triage.json` — edit and re-run. Length lines (`length_warn`,
`nloc_warn`) only nominate; the teeth are the structural (`density_tangled`, `nesting_bad`, `ccn_hard`) and
codebase-relative (`z_cut`, `min_population`) knobs, plus the inverse-smell knobs (`shallow_max_loc`,
`delegation_dup_min`). Framework-idiomatic decorators (`@op`/`@job`/`@asset`/route/`@fixture`) are excluded so
dagster + FastAPI glue is never mistaken for classitis.

## Dependencies

`lizard` (numeric metrics, ~20 languages) + `tree-sitter` (structural: true nesting, delegation, decorators),
pinned in `scripts/requirements-test.txt`. The engine's own suite is `scripts/tests/test_complexity_triage.py`
(8 cases) and the wrapper's is `scripts/tests/complexity.bats` (7 cases). Bump a pin only with both green.

## Posture — the degree IS the autonomous gate (ON)

Run bare, it's advisory (prints, exits 0). `--gate` **blocks**, and CI runs `--gate`. The gate is **autonomous
and degree-driven**: it fails the build on the **clearly-bad, high-degree findings** — a **high-confidence
`TANGLED`** or any **`SHALLOW`** — while **medium/low `TANGLED`, `OUTLIER_REVIEW`, `DEEP` stay advisory**. No human
decides per run; the degree the three stages converge on IS the stop-or-accept decision, made per finding. The bar
is a knob (`gate_confidence`, `gate_shallow` in `scripts/complexity-triage.json`). It could only be turned on FROM
a run — the codebase's own distribution set the bar, and after the B162 remediation there are **zero
high-`TANGLED`/`SHALLOW`**, so the gate passes today (the one residual is a medium/adjudicated `TANGLED`) and blocks
only *new* clear complexity debt. Loosen or tighten by moving `gate_confidence` (`low`|`medium`|`high`).

## Threshold alignment — CodeScene and SonarQube

The lab's *reading* lives in this engine; the two scanners stay as independent second opinions.

- **CodeScene** — **no change; stays on defaults.** Its Code Health is already a composite (Large Method weighed
  against Complex Method / Bumpy Road / nesting), not a length verdict, and it runs advisory (github-app + MCP),
  not a merge gate. There is deliberately **no committed rules file** — a defaults-matching file would be noise,
  and the lab's depth-aware reading is the triage engine, not a tweak to CodeScene's length rule.
- **SonarQube** — **confirmed live in-cluster 2026-09-21** (the Sonar API is behind the Keycloak forward-auth, so
  a host-side call hits the login wall; query from inside the pod, `weyland/sonarqube-*`). The project runs the
  **built-in "Sonar way"** profiles for every language. Relevant active rules: **`python:S3776` / `java:S3776`
  Cognitive Complexity (threshold 15)** — the depth-aware signal we want — *and* **`S138` "too many lines"**
  (`python` max 100, `java` max 75) — raw method length, the signal B162 says is not a defect on its own.

  **Decision: keep the built-in profile as-is; do NOT create a custom profile to deactivate `S138`.** SonarQube
  can't edit a built-in profile — deactivating a rule means copying "Sonar way" to a custom profile and
  reassigning the project, which then stops tracking Sonar's per-version rule updates and becomes a maintenance
  liability (a poor trade for a solo $0 lab). After the B162 refactor almost nothing trips `S138` (100/75 is
  lenient); where a genuinely deep function does, **the triage engine is the lab's authoritative reading** and the
  `S138` smell is a triaged known-non-issue, not a driver. `S3776` cognitive complexity is already the active,
  depth-aware gate — so Sonar stays the "second opinion" this posture intends, with zero maintenance. The read is
  read-only; confirm it again with:

  ```
  kubectl -n weyland exec <sonarqube-pod> -- sh -c 'curl -s -u admin:$SONAR_ADMIN_PW "http://localhost:9000/api/rules/search?activation=true&languages=py,java&ps=500&f=name,params"'
  ```

  **If you ever DO want `S138` off** (reversible): copy the profile, deactivate the rule, reassign the project —
  `POST /api/qualityprofiles/copy` (`fromKey=<py Sonar way key>`, `toName=Weyland way`) → `POST
  /api/qualityprofiles/deactivate_rule` (`key=<new>`, `rule=python:S138`) → `POST /api/qualityprofiles/add_project`.

## CI wiring

The `complexity-triage` step in `.woodpecker.yml` runs the triage **with `--gate`** on every build — it BLOCKS on
a high-confidence `TANGLED` or any `SHALLOW`, and reports the rest. (image `python:3.12-slim`, installs
`scripts/requirements-test.txt`, runs `bash scripts/check-complexity.sh --gate`.) Not in `quality-tools.yaml` —
that registry is the scan *suite* (SonarQube/CodeScene/scan-suite); this is a repo-guard like the other
`check-*.sh`. To temporarily run it non-blocking, drop the `--gate` flag (or raise `gate_confidence`).

## Remediation log — the B162 pass (2026-09-21)

The first run found **20 TANGLED + 2 SHALLOW** across the real-code services. Nineteen were refactored to deep
modules (verified: the named test suite stayed green, and the triage re-run confirmed each cleared) and one was
adjudicated acceptable. Zero behavior change.

- **`datahub_emit.py` (7):** `_field_class` (rule chain → data table), `emit_dbt`, `emit_applications`,
  `emit_source_terms`, `emit_mesh_glossary` (each split into cohesive per-phase helpers),
  `emit_asset_check_assertions` (`_emit_assertion` + `_emit_table_assertions`), `emit_field_docs`
  (`_resolve_field_doc` + `_apply_field_docs`). Guarded by `test_datahub_emit.py`.
- **`loaders.py` (2):** `_load_dataset_to_cassandra` (`_cassandra_write_file`), `_build_vectors`
  (`_read_vector_frame` + `_vectors_from_frame`). Guarded by `test_loaders.py`.
- **Store writers (4):** `neo4j_write`, `weaviate_write`, `pgvector_write` (`_write_source` each), `eval_scores`
  (`_persist_scores` + `_log_judge_error`). Untested integration code (`assets/*.py`, excluded from coverage by
  design) — verified by compile + triage-clear + pure code-motion.
- **Other assets (3):** `extract_epub` (`_opf_path` / `_parse_opf_spine` / `_all_html_chapters`, guarded by
  `test_kindle_text_parse.py`), `collect_source_documents` (`_clone_repo` / `_read_document` / `_walk_documents`),
  `_produce_dataset` (`_produce_rows`).
- **`scripts` (2):** `machine_inventory.cmd_merge` (`_merge_new_packages` / `_prune_absent`, guarded by
  `machine-inventory.bats`); `complexity_triage._numeric_verdict` (`_signals` / `_tangled_confidence`) +
  `_numeric_findings` (`_gather_functions` / `_population_stats` / `_zscores` / `_finding_for`) — the tool now
  passes its own triage, guarded by its 8 tests.
- **SHALLOW (2):** the `finance_common.py` / `music_common.py` / `health_common.py` facades re-declared the same
  `client()` and `download()` pass-throughs → converted to re-exports (the repo-binding `*_put`/`*_fput` stay).

**Adjudicated acceptable (not refactored):** `loaders.py:build_store_load_assets`. It is a per-store asset
registry — ~11 near-identical `if cfg.<store>_allow: @asset …` gates — with **density 0.17** (well below the
0.28 tangle line) and nesting 4; the `ccn=20` is just the sum of the per-store gates. Clearing the verdict would
mean converting the gates to a data-driven factory table, relocating ~250 lines of live dagster asset
registration (names/groups/deps the running pipeline depends on) for a cosmetic verdict change, not a genuine
complexity reduction. This is the design's "long but not tangled → acceptable" case — the human-glance the triage
prescribes.
