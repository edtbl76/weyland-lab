# Demo — Model Catalog

Dagster keeps a Postgres registry (`model_catalog`) of every reachable hosted/local model fresh, so
the tool-server's `/models` reflects what's routable without a live fetch on every call. The
`weyland_catalog_job` (asset group `catalog`) fetches **all** models from three sources —
OpenRouter `/models`, the Gemini model list, and Ollama `/api/tags` — records a per-row `free`
boolean, and prunes replace-by-source (`DELETE WHERE source=…` then re-INSERT). Scheduled every 6h
at `:50` (`weyland_catalog_schedule`, cron `50 */6 * * *`) and idempotent. The `model_catalog` table
is also cataloged into **DataHub** (ML & Modeling domain) by the catalog-emit job.

## Sequence diagram

Reuse the existing diagram: **[../diagrams/flow-model-catalog.md](../diagrams/flow-model-catalog.md)**
(Dagster schedule → `weyland_catalog_job` → OpenRouter / Gemini / Ollama → Postgres `model_catalog`
→ tool-server `/models`).

## Prerequisites

- `mother` — hosts Dagster, the in-cluster Postgres (`weyland-postgres.weyland.svc:5432`, no
  NodePort), and the tool-server (`http://mother:30080`).
- `rogueone` — Ollama at `ollama.weyland.lab:11434` (one of the three catalog sources).
- Human-gated egress (the LiteLLM valve) open for the OpenRouter + Gemini fetches.
- Dagster UI at `dagster.weyland.lab`; DataHub at `datahub.weyland.lab`. Login `emangini` /
  `weyland_dev_password`.

## UI walkthrough

1. Open `https://dagster.weyland.lab` → **Automation** → `weyland_catalog_schedule` (RUNNING, cron
   `50 */6 * * *`).
2. Open **Jobs** → `weyland_catalog_job` → **Materialize** the `catalog` group to refresh now.
   Watch the run fetch the three sources and upsert `model_catalog`.
3. Verify the result surfaces on the tool-server OpenAPI page: `http://mother:30080/docs` →
   **GET `/models`** → **Try it out** → **Execute** — the list reflects the refreshed table.
4. In `https://datahub.weyland.lab`, search **`model_catalog`** (ML & Modeling domain) to see the
   cataloged table (column schema comes via the DataHub Iceberg source / `iceberg_publish`).

## CLI walkthrough

Read what the tool-server routes (the live view of `model_catalog`):

[mother] `curl -s http://mother:30080/models`

Trigger a refresh now (the `catalog` group is not in the `/pipeline/trigger` enum, so run the job
in the user-code pod):

[mother] `kubectl -n weyland exec deploy/dagster-user-code -- dagster job execute -j weyland_catalog_job -m weyland_pipeline.definitions`

Inspect the Postgres table directly (in-cluster only — exec into the Postgres pod):

[mother] `kubectl -n weyland exec deploy/weyland-postgres -- psql -U weyland -d weyland -c "SELECT source, count(*), sum(free::int) AS free FROM model_catalog GROUP BY source ORDER BY source;"`

Spot-check a few rows:

[mother] `kubectl -n weyland exec deploy/weyland-postgres -- psql -U weyland -d weyland -c "SELECT source, model, free FROM model_catalog ORDER BY source LIMIT 10;"`

> The exact `model_catalog` column names beyond `source` / `model` / `free` are `TODO: verify`
> against the live schema (`\d model_catalog`); the grouping above uses only the documented columns
> from [../diagrams/flow-model-catalog.md](../diagrams/flow-model-catalog.md).

## Expected result

- The Dagster run succeeds; `model_catalog` is repopulated (one block of rows per source:
  `openrouter`, `gemini`, `ollama`).
- `GET /models` returns the selectable model list, matching the refreshed table.
- Re-running changes nothing structurally (replace-by-source is idempotent).
- DataHub shows the `model_catalog` dataset under the ML & Modeling domain.

## Cleanup / teardown

The refresh is **replace-by-source and idempotent** — it maintains a live lookup table, not test
data, so the normal state is to leave it populated. If you must clear a source you added for
testing:

[mother] `kubectl -n weyland exec deploy/weyland-postgres -- psql -U weyland -d weyland -c "DELETE FROM model_catalog WHERE source='<source>';"`

Re-running `weyland_catalog_job` restores it. The DataHub `model_catalog` entity is an idempotent
upsert (soft-delete via the DataHub UI if a test entity must go).
