# Open Food Facts → vector stores — implementation plan (B78 thread (a), EMA-69)

**Status: PLANNED, not started.** Written 2026-08-27 after scoping revealed the work is a read-path
change to shared code, not the config entry the backlog implies.

The backlog describes this thread as "reuses the `build_vector_load_assets` loader + `vector_spec`
already built for the other sets; just add the OFF spec + run." That is not accurate. The shared
vector builder cannot read a source this size, and adding the spec without changing it OOMs the
Dagster user-code pod. This document is the corrected scope.

| | |
|---|---|
| Backlog | `docs/backlog.md` → B78 thread (a) |
| Linear | EMA-69 (bucket parent; this thread has no child issue) |
| Grid intent | `docs/data-domain-storage-grid.csv` — OFF row: `Qdrant=Y (product similarity)`, `Weaviate=Y (product similarity)`, `LanceDB=Y` |
| Actual state | none of the three hydrated; `HEALTH_CFG.vector_allow` has `big_five` only |
| Touches | `datasets_lib/loaders.py`, `datasets_health_transform.py`, first pytest suite in `weyland-dagster`, 4 docs, image build + redeploy |

---

## Why this is not small

### 1. The read path cannot hold this source (blocking)

`_build_vectors` (`datasets_lib/loaders.py:694`) reads every silver parquet file **whole** into one
pandas frame before doing anything else:

```python
mc.fget_object(cfg.repo, obj.object_name, tmp.name)
frames.append(pd.read_parquet(tmp.name))
...
df = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
```

OFF's silver is a **single** parquet file written by `build_streamed_parquet_asset` — the streaming
writer that exists precisely because the broker OOMs on this source. It is ~4.5M rows across 211
columns, and the streamed writer forces `dtype=str` (OFF is sparse and type-mixed across 200+
columns, so type inference blows up mid-stream). All-string, all columns, all rows, in pandas.

Runs execute in the **user-code pod**: `requests.memory 1.75Gi`, `limits.memory 12Gi`, `Recreate`
strategy, on a node whose own manifest comments call it "~98% committed." The read OOMs long before
the embedder is reached, and a pod OOM on mother is an outage, not a failed run.

Every other dataset in `vector_allow` is small enough that this never surfaced. `big_five` is ~20k
rows. The defect is latent, not new — OFF is just the first source large enough to trigger it.

**A cap alone does not fix this.** The backlog's proposed `{"text": [...], "cap": 200000}` truncates
*after* the frame is built. The read is what fails. The cap has to be applied during the read.

### 2. The text spec fails silently when its columns are wrong

```python
cols = [c for c in spec["text"] if c in df.columns]
texts = df[cols].fillna("").astype(str).agg(" ".join, axis=1).tolist()
```

Columns not present are dropped with no warning. If **every** named column is missing, `texts`
becomes a list of empty strings, bge-small embeds them, and the loader reports a successful
hydration of N identical vectors. Nothing raises, nothing logs a problem, and the collection looks
populated in Qdrant and in DataHub.

This matters immediately, and the observed schema (Phase 0, 2026-08-31) proves it — by inverting the
assumption everyone held. The backlog proposes `product_name` + `brands` + `categories_en`, and
`datasets_field_docs.OPEN_FOOD_FACTS` documents `categories` and `categories_fr` with *no*
`categories_en`, so the field docs made `categories_en` look like a typo. Reading the real file
settled it the other way: the silver parquet **has** `categories_en` (and `categories`,
`categories_tags`) and does **not** have `categories_fr`. The repo's field docs are stale relative to
the downloaded OFF export; the backlog's `categories_en` was correct all along, and "correcting" it to
`categories_fr` — the intuitive fix from the docs — is what would have silently embedded a third of
the text signal as empty and reported success. The lesson is not which column won; it is that a column
name copied from *any* declared source, docs included, is a guess until the file confirms it.

This is the absence-as-success class recorded in `project.md` (learned 2026-08-22, five instances in
one session). Fixing it belongs in this pass because this is the change that would otherwise
introduce a sixth.

### 3. One config entry hydrates three backends

`lancedb_allow` defaults to reusing `vector_allow`. Adding OFF to `vector_allow` therefore targets
**Qdrant, Weaviate and LanceDB** in the same change. That is the correct outcome — the grid declares
`Y` for all three — but it triples the verification surface and it is not what "add the OFF spec"
sounds like.

### 4. No tests exist in this service

`services/weyland-dagster/` has no `test_*.py`, no `conftest.py`, and no pytest configuration. Per
`team.md` (Testing Posture, affirmed 2026-08-22) the methodology is **TDD, Red first**. This change
therefore also stands up the service's first test harness — the same situation as the shell/bats
gap, one tier up.

---

## Plan

Ordered. Each phase is independently verifiable; phases 1–2 are shippable without phase 3 running.

### Phase 0 — confirm the source before writing the spec

Do not copy column names from the backlog. Read the actual silver schema and confirm, on the real
file: row count, column count, and the presence and null-density of the candidate text columns
(`product_name`, `brands`, `categories`). Record the observed figures in this document.

`project.md` (learned 2026-08-22): "Before encoding any external command's output in a stub, observe
the real thing once." Same rule applies to a schema.

**Observed 2026-08-31** (read inside `dagster-user-code` via `io.client()` against lakeFS `health`):

- Single file: `main/parquet/open_food_facts/open_food_facts.parquet` — **211 columns**,
  **4,532,765 rows**, every column `large_string`. Confirms the 4.5M / all-string / whole-read-OOM
  premise exactly, and that it is one file (so the projected read iterates row groups within it, not
  across many files).
- Candidate text columns **present**: `product_name`, `brands`, `categories`, **`categories_en`**,
  `generic_name`. Category variants that exist: `categories`, `categories_tags`, `categories_en`.
- **`categories_fr` is absent.** The field docs are stale; the file is authoritative.
- Id: `code` (barcode) present; `url` present for payload.
- Null-density: TODO — measure on the projected read in Phase 1 (a cheap `count`/`count_if(x <> '')`
  over `product_name`, since `na_filter=False` at ingest means "missing" is the empty string, not
  null).

### Phase 1 — bounded read in `_build_vectors` (TDD)

Replace the whole-file `pd.read_parquet` with a projected, capped, streaming read:

- `pq.ParquetFile(path).iter_batches(columns=needed, batch_size=...)`, where `needed` is only the
  columns the spec actually references (`text` / `numeric` / `payload` / `id`). For OFF that is 3–5
  of 211 columns.
- Apply the row filter during iteration (non-empty `product_name`), not after.
- Stop once `cap` rows are collected; leave remaining batches unread.
- Memory becomes a function of `batch_size × len(needed)`, independent of source size. This retires
  the class for every future large source, not just OFF.

New `vector_spec` keys: `cap` (int) and `filter` (column that must be non-empty). Both optional;
absent means current behaviour, so no existing dataset changes.

**Fail closed** where it currently fails silently:

- a `text` spec resolving to zero present columns raises, naming the missing columns and the columns
  that do exist;
- a spec whose `filter` column is absent raises rather than silently passing every row;
- a run that collects zero rows raises rather than creating an empty collection.

Red first: the empty-columns case, the missing-filter-column case, and the cap-stops-early case all
get a failing test before the implementation. Assert the failure **reason**, not just that something
raised — `project.md` (learned 2026-08-23) records a bats test that passed against a function which
did not exist.

Bounded-memory behaviour is asserted with a synthetic wide parquet fixture (many columns, many rows)
and a check that only the projected columns are materialised. A test that merely runs the function
proves nothing about memory.

### Phase 2 — the OFF spec

In `HEALTH_CFG.vector_allow`, using the column names confirmed in Phase 0:

```python
"open_food_facts": {
    "text": ["product_name", "brands", "categories_en"],  # all confirmed present in Phase 0
    "filter": "product_name",
    "cap": 200_000,
    "id": "code",               # the barcode — a real key, better than a row index
    "payload": ["product_name", "brands", "url"],          # confirmed present; `url` is a usable link
},
```

`categories_en` (the observed English-normalized column, e.g. `en:snacks,en:sweet-snacks`) is the
confirmed name — NOT `categories_fr`, which the file does not have. `categories` (raw human text) is
also present and is a defensible alternative if the `en:`-prefixed tag format reads worse in
similarity results; decide at implementation. `payload` columns still drop silently if absent
(loaders.py:744) — the fail-closed guard added in Phase 1 covers `text`/`filter`/`id`, so keep payload
to columns confirmed in Phase 0 (`product_name`, `brands`, `url` all are).

`id: code` is a deliberate improvement over the row-index default: OFF has a natural key, and a
payload `row_id` that means something makes the collection usable for lookups, not just similarity.

Confirm `streamed_parquet` already causes the store loaders to depend on
`datasets_health_open_food_facts_parquet` rather than the broker's `datasets_health_parquet`. If it
does not, the vector loader reads a path that does not exist for this dataset.

### Phase 3 — run and verify, per backend

Expected shape at cap 200k, per the backlog's own arithmetic: 200k × 384 × 4B ≈ **~300 MB of vectors
per backend**, embed time ~20–30 min on CPU. Verify against the real run rather than trusting the
estimate.

Watch the user-code pod's memory through the run. The in-memory `records` list (200k Python lists of
384 floats plus payload dicts) is the remaining peak after Phase 1 and is roughly 2 GB — inside the
12Gi limit but not trivially so. If it proves tight, the upsert loop batches; the read no longer
does.

Per backend, assert a query returns sensible neighbours — not just that the collection exists with a
row count. A populated collection of near-identical vectors is exactly what defect 2 produces.

### Phase 4 — cascade

See the table below. The self-maintaining legs are **verified**, not assumed.

---

## Cascade inventory

### Self-maintaining — verify, do not edit

| Leg | Why it needs no change |
|---|---|
| DataHub Qdrant catalog | `emit_qdrant()` enumerates collections **live** from the server |
| DataHub Weaviate catalog | `emit_weaviate()` enumerates classes live |
| Description + lineage | `_vector_dataset_meta` matches on `datasets_<domain>` generically; resolves lineage to `datasets_health_<backend>_load` with no per-dataset entry |
| Stats tab | `_emit_profile` emits rowCount for custom-emitted store datasets |
| Data contracts | B80 emits per-dataset, querying the live assertion set |
| Ghost cleanup | `_reconcile_platform` soft-deletes catalog entries whose collection disappears |

Verification is a DataHub read after the emit job, confirming the three new entities carry
description, lineage, and a non-zero rowCount. "It should be automatic" is not evidence.

### Manual

| Leg | File |
|---|---|
| The spec | `assets/datasets_health_transform.py` |
| Bounded read + fail-closed | `assets/datasets_lib/loaders.py` |
| First test suite | `services/weyland-dagster/tests/` |
| Hydration runbook | `docs/runbooks/datasets-hydration.md` — three literal "OFF → B78" markers (lines ~211, ~286, ~287) plus the two ledger rows |
| Backlog | `docs/backlog.md` → B78 thread (a) |
| Storage grid | `docs/data-domain-storage-grid.csv` — see drift note below |
| Image + deploy | build, tag, bump `user-code.yaml`, redeploy (`Recreate`, brief code-server blip) |
| DoD | the 8-pillar gate, including the Pillar 8 cascade check |

### Genuinely absent — flagged, not folded in

- **No Grafana dashboard exists for any vector store.** Qdrant, Weaviate and LanceDB have no panels,
  so three new collections land invisible to the monitoring surface. Real gap, but it is a vector-store
  observability item, not an OFF item. Note it; do not build it inside this thread.
- **No quality checks cover any vector store.** `build_asset_checks` covers silver parquet only. Same
  reasoning: real gap, separate scope.

### Pre-existing drift found while scoping

`docs/data-domain-storage-grid.csv` records OFF as `OpenSearch=N`, but
`HEALTH_CFG.opensearch_allow` includes `open_food_facts` and the hydration runbook lists it as an
OpenSearch target. Declared intent disagrees with running code — the same class as B148, benign this
time because the code is the more permissive side. The grid comment in `config.py` already states the
code is the source of truth; the grid cell should be corrected to match.

---

## Open decisions

1. **Does LanceDB take the cap, or the full 4.5M set?** `lancedb_allow`'s comment suggests LanceDB
   could hold more than the server backends because it reads from object storage. Recommendation:
   **cap all three at 200k.** Embedding 4.5M texts is hours of CPU regardless of where the vectors
   land, and three backends holding the same vectors is what makes them comparable, which is the
   reason for running three.
2. **Cap value.** 200k comes from the backlog. Phase 0's observed non-empty `product_name` count may
   argue for a different number.

---

## Verification

- Phase 1 tests fail before the implementation and pass after, asserting failure *reasons*.
- A wide-parquet fixture proves only projected columns are read.
- Real run completes without the user-code pod exceeding its limit; peak RSS recorded here.
- Each of the three backends returns plausible nearest neighbours for a known product, by hand.
- DataHub shows three new vector datasets with description, lineage and rowCount.
- No existing vector dataset changes: `big_five` and the eight music sets re-hydrate identically.
- Grid, runbook and backlog agree with the code afterwards.
