# Demo — Model-Eval Leaderboard data product (B84 P1)

The B4/B96 judge-panel RAG leaderboard, **productized**: a governed, browsable **DataHub Data Product** (owned, with a
validity+freshness **Data Contract**), a **Superset dashboard**, and a **Port** launcher link — *"which model wins, on
what, as of when."* Rides entirely on the done B4 eval pipeline + B96 golden set. Built + validated 2026-07-24.

Grounded in `datahub_emit.py` (`_PRODUCTS` / `emit_eval_assertions`), the tool-server `/evals/leaderboard`, and
[runbooks/eval-harness.md](../runbooks/eval-harness.md).

## The surfaces

| Surface | What | URL |
|---|---|---|
| **DataHub Data Product** | 9 eval datasets, owner, Data Contract | `datahub.weyland.lab` → Domains → ML & Modeling → Data Products → Model-Eval Leaderboard |
| **Data Contract** | validity + freshness assertions on `eval_scores` | the product's `eval_scores` → **Data Contract** tab |
| **Superset dashboard** | per-model bars + faithfulness trend | `https://superset.weyland.lab/superset/dashboard/15` |
| **Port launcher** | one-click endpoint | Port → `endpoint` → *Model-Eval Leaderboard (Superset)* |

## CLI walkthrough

The leaderboard data (the panel-averaged latest scored run), served by the tool-server (mother):
```
[mother] kubectl -n weyland exec deployment/weyland-tool-server -- python -c "import urllib.request,json; d=json.loads(urllib.request.urlopen('http://localhost:8080/evals/leaderboard').read()); print('run', d['run_id']); [print(r['model'], r['faithfulness'], r['answer_relevancy'], r['context_relevancy']) for r in d['leaderboard']]"
```
Re-emit the catalog (product + ownership + contract + link) — Dagster UI → `datahub_catalog_emit_job` → Launch, or watch the ops: `emit_data_products_op` → `(10, N)`, `emit_eval_assertions_op` → `2` assertions + the Data Contract.

## UAT — eyes-on (each surface)

1. **DataHub product** — the page renders: name, **ML & Modeling** domain, description, **Owner = emangini**, the
   **Assets** tab lists the eval datasets, and **Resources** links to the Superset dashboard.
2. **Data Contract** — `eval_scores` → **Data Contract** tab shows an **ACTIVE** contract; its **Assertions** tab shows
   `eval-leaderboard-validity` + `eval-leaderboard-freshness`, both **green**.
3. **Superset dashboard** — open dashboard 15: the **bar chart** (6 models × faithfulness/answer/context) and the
   **trend line** (faithfulness across runs) both render, with the Markdown header + trend caveat.
4. **Port** — the `endpoint` *Model-Eval Leaderboard (Superset)* resolves to the dashboard.

## Expected result

- A catalogued, owned, contract-backed data product whose Resources link + Port endpoint both open the live Superset
  leaderboard. The bar chart shows the latest scored run's per-model scores; the contract's two assertions are green.

## Caveats

- The **trend line conflates the B96 depth-sweep runs** (retrieval limit 3/5/8), not repeated same-config runs — read
  the slope as config differences, not degradation. A clean trend needs repeated same-config runs (fast-follow).
- **Freshness is loose** (90d) by design — evals are on-demand (~40–70 min, fired deliberately), not scheduled, so a
  hard SLA doesn't fit; the assertion is a "has-a-recent-scored-run" signal, not a cadence guarantee.

## Cleanup / teardown

Read-only — no data created beyond DataHub metadata (product/assertions/contract/link, all idempotent re-emits) + the
Superset charts/dashboard (definitions, not data). Nothing to tear down.
