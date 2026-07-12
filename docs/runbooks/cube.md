# Cube — the semantic / metrics layer (B1.7 L6)

Cube is the **serving semantic layer**: you define business metrics + dimensions **once** as *cubes* over the dbt
marts, and every consumer — BI tools, apps, notebooks, agents — queries those *same* governed definitions through
one of three APIs (**SQL**, **REST**, **GraphQL**). It sits *between* the marts and whatever consumes them. Runs in
`data-mesh`, manifests in `k8s/cube/cube.yaml`, UI at `https://cube.weyland.lab` (Keycloak-gated).

**Status: DEPLOYED 2026-07-12** (first build after B79 freed the node). 7 cubes over the marts, connected to Trino
via the `trino-noauth` proxy, SQL API proven end-to-end.

---

## 1. What it buys you — and how it differs from what we already have

This is the part to be honest about, because the mesh already has a lot of overlapping pieces.

| Layer | What it is | Consumed by |
|---|---|---|
| **dbt marts** (`iceberg.dbt.mart_*`) | The tested, curated business *tables* | Everything downstream |
| **Lightdash** | dbt-*native* BI — builds dims/metrics from the dbt project | Humans, in a BI UI |
| **Superset** | Ad-hoc SQL BI over any Trino catalog | Humans, in a BI UI |
| **dbt MetricFlow** | Metric *definitions* declared in the dbt project | dbt SL / Cube / BI |
| **Cube** | A **semantic API** — metrics defined once, served over **SQL + REST + GraphQL** | **BI tools *and* apps / agents / LLMs / notebooks** |

**Cube's distinctive value in THIS stack** (be clear — much of it overlaps dbt + Lightdash):
1. **A governed metrics API for NON-BI consumers.** Lightdash/Superset are BI *UIs* — a human clicks charts. Cube
   is an *API*: an app, an **agent (Hermes)**, or an LLM can ask "avg life expectancy in country X" over REST/GraphQL
   and get the *same governed number* a dashboard would. That's the thing nothing else here does.
2. **One metric definition, many protocols.** `avg_danceability` is defined once; SQL clients, a React app, and a
   GraphQL query all get the identical `avg(danceability)` compiled to Trino — no drift.
3. **Pre-aggregation / caching** (Cube Store, bundled) — pre-computes rollups so dashboards hit cached aggregates
   instead of re-hammering Trino. A speed win *if* BI gets slow; not needed at small scale.

**When to reach for Cube vs the alternatives:**
- Human wants to explore/build a dashboard → **Lightdash** (dbt-native) or **Superset** (ad-hoc). *Not* Cube.
- An **app / agent / LLM** needs a consistent, governed metric over an API → **Cube** (REST/GraphQL).
- A BI tool wants to consume Cube's governed metrics (not raw Trino) → point it at Cube's **SQL API** (`:15432`).
- If you only ever do BI-by-humans, Cube is largely redundant with dbt + Lightdash — keep it minimal (headless).

---

## 2. Architecture

```
consumers (BI / app / agent / notebook)
      │  SQL(:15432, pg-wire) · REST/GraphQL(:4000)
      ▼
   Cube  ──model (cubes: measures + dimensions)──►  compiles to Trino SQL
      │
      ▼  (trino-noauth proxy strips the Basic-auth header, like Soda/Lightdash)
   Trino ──► iceberg.dbt.mart_*  (the dbt marts, on Nessie/MinIO)
```

- **DB connection:** `CUBEJS_DB_TYPE=trino`, host `trino-noauth.data-mesh:8080`, user `dbt`, catalog `iceberg`.
  Same no-auth path Soda/Lightdash use (Cube's Trino driver forces Basic auth → the nginx proxy strips it → Trino
  sees only `X-Trino-User: dbt`; Ranger authorizes `dbt` on `iceberg.dbt`).
- **Model:** 7 cubes in a ConfigMap (`cube-model`), one per mart (`spotify_audio`, `country_health`, …). Measures
  = the aggregations (`avg_danceability`, `total_plays_sum`), dimensions = the group-bys (`track_genre`, `country`).
- **APIs:** REST + GraphQL + Playground on `:4000`; **SQL API** (Postgres-wire) on `:15432` (`cube`/`weyland_dev_password`).
- **Access:** `cube.weyland.lab` behind Keycloak forward-auth (data-mesh `Middleware` → shared `traefik-forward-auth`).

---

## 3. Using it

**SQL API** — the main integration surface (any pg client / BI tool):
```
PGPASSWORD=weyland_dev_password psql -h cube.data-mesh.svc.cluster.local -p 15432 -U cube -d cube \
  -c "SELECT track_genre, MEASURE(avg_danceability) FROM spotify_audio GROUP BY 1 ORDER BY 2 DESC LIMIT 5;"
```
⚠️ **Measures MUST be wrapped in `MEASURE()`** — `SELECT track_genre, avg_danceability …` fails with "could not be
resolved from available columns". Dimensions select normally; measures go through `MEASURE()`.

**REST** — `POST https://cube.weyland.lab/cubejs-api/v1/load` with a JSON query `{"measures":["spotify_audio.avg_danceability"],"dimensions":["spotify_audio.track_genre"]}` (needs a JWT signed with `CUBEJS_API_SECRET`).

**Adding a cube:** edit `data.marts.yml` in `k8s/cube/cube.yaml` (a cube = `sql_table: dbt.<mart>` + `measures` +
`dimensions`), re-apply. The model is mounted via **`subPath`** (see gotchas), so a redeploy is needed to reload.

---

## 4. Gotchas

- **Model mount uses `subPath`** — a bare ConfigMap *directory* mount also exposes the `..data/` symlink dir, which
  Cube's model globber loads too → **"Found duplicate cube name"**. `subPath: marts.yml` mounts just the file.
  Cost: no hot-reload on ConfigMap change — redeploy to update the model.
- **SQL API needs `MEASURE()`** (see §3).
- **The Playground is a DEV tool, not the UI** — dev mode (`CUBEJS_DEV_MODE=true`) serves the Playground, which is
  a heavy client-side SPA that recompiles the schema + auto-runs preview queries → **freezes the browser** with many
  cubes. The *server* is tiny (~214 Mi). For a serving deployment, flip `CUBEJS_DEV_MODE=false` (headless, no
  Playground) and consume via the SQL API from Superset/Lightdash, or via REST from apps.
- **`:latest` bundles Cube Store** (rocksdb metastore + cachestore, constant background checkpointing). Fine, but
  pin the image (OPA no-latest = dry-run/warn) once verified.
- **KEEP dev mode on a single node.** Dev mode bundles Cube Store so it "just works". **Production mode
  (`CUBEJS_DEV_MODE=false`) requires an EXTERNAL Cube Store** (`CUBEJS_CUBESTORE_HOST`) — without it the SQL API
  errors "Cube Store was specified as queue/cache driver". That's pure overhead here (we run live Trino queries, no
  pre-aggs). The *server* is tiny (~214Mi); only the browser Playground is heavy, and only when opened — so dev mode
  + not-opening-the-Playground is the right lab setup. Deploy a standalone Cube Store only if you add pre-aggregations.
- **Consumed by Superset** via the SQL API (add DB `postgresql://cube:…@cube.data-mesh.svc:15432/cube`). Chart cubes
  with **virtual datasets** (SQL Lab, `MEASURE(...)`) — Superset's auto-generated `AVG()` SQL is rejected by Cube.

---

## 5. Follow-ups
- Pin the image to a digest; register an **Argo Application** (`k8s/argocd/applications/cube.yaml`) — currently
  `kubectl apply`-ed, not GitOps-managed.
- **MetricFlow** (the other half of B1.7) — `semantic_models` + `metrics` in the dbt project.
- Wire **Superset → Cube SQL API** so BI consumes governed metrics, not raw Trino. See [[dbt-transform-tier]], [[cube-semantic-layer-b1.7]].
