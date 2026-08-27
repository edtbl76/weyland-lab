# B82 — Application Taxonomy (cross-surface app classification)

**Status:** ✅ BUILT + DONE (2026-08-05). Sub-issue of B80. Linear EMA-73.

> **⚠️ This is the design-time record — some of it is SUPERSEDED by what shipped. Current facts:**
> **(1) Registry path** is `services/weyland-dagster/weyland_pipeline/applications.yaml` (NOT the `config/…` in §3/§5/§6
> below — only in-build-context files bake into the Dagster image). Tofu reads it at
> `../../services/weyland-dagster/weyland_pipeline/applications.yaml`.
> **(2) Final roster** is **29 DataHub Applications + 25 pure-compute = 54 components** (the §4 draft was ~26). The
> Argo-driven completeness pass reclassified: **grafana** → data-app (owns ~367 datasets), **nessie + lakefs** added as
> data-apps (cataloged DBs), **ranger** confirmed operational data-app; pure-compute grew to 25 (the full app fleet).
> **(3) Live roster of record** = the registry itself + [docs/concepts/application-catalog.md](../concepts/application-catalog.md)
> + arch §7f, not the §4 table below. **(4) Enrichment shipped:** docs link · tag · domain · customProperties · 30-term
> Capabilities glossary (DataHub) + a `capabilities` array on all 54 Port components. Drift guard:
> `scripts/check-app-registry.sh`.

## 1. What this is

Adopt DataHub's **Application** entity to give the catalog an *app-centric* lens — "what does app X own / produce /
consume?" — **alongside** the existing business **Domains** (Music/Health/…) and **Data Products** (bundles).

But the moment apps become first-class, the classification stops being a DataHub-only concern. The **same set of app
lines** has to hold across four surfaces or the system reads as incoherent:

| Surface | What it holds |
|---|---|
| **DataHub** | `Application` entities + every dataset/chart/dashboard attached to its owning app |
| **Port** | the `component` / `k8s_workload` catalog — each app flagged as a data-app + linked to its DataHub Application |
| **Docs** | `arch.md` app-taxonomy section + a new `concepts/application-catalog.md` |
| **Diagrams** | the LikeC4 model + `platform-map.html` reflect the same app set + ownership |

This is the DoD's new *"one source of truth for a cross-surface taxonomy"* process (added 2026-08-05): the
classification is defined **once** and every surface consumes or is DoD-checked against it. Drift becomes impossible
by construction, not by discipline.

## 2. The classification line

An app is a **DataHub Application** iff it **owns cataloged data now, OR plausibly will** (it has, or will have, a
backing store that lands in the catalog). Everything else is **pure compute** — it lives in Port's component catalog
only, never as a DataHub Application (an empty Application entity is noise).

- **Data-plausible → DataHub Application + Port component** (with a link between them).
- **Pure compute → Port component only.**

Rationale for "plausibly will": modeling an app that will own data later means future assets attach to an entity that
already exists — no retro-fit. But the bar still excludes services that will *never* own a dataset (a KEDA scaler, a
TTS pod, a stateless proxy), which would otherwise duplicate Port's full inventory and create a second, drifting app
catalog.

## 3. The canonical registry (the source of truth)

A single machine-readable file — **`config/applications.yaml`** (platform root, baked into the Dagster image AND
readable by Tofu) — is the ONE definition. Every surface reads or is checked against it.

**Schema (per app):**

```yaml
- key: weyland-dagster          # stable id (matches the Port component + k8s workload name)
  name: Weyland Dagster         # display name (DataHub Application + docs)
  group: core-producer          # core-producer | ai-serving | data-platform | bi | operational | pure-compute
  datahub_application: true      # false → Port-only pure compute
  owns:                          # URN substring patterns (producer-based, first-match, like _DOMAIN_RULES); [] if none yet
    - "datasets_"
    - "qdrant"
    - "weaviate"
  port_component: weyland-dagster  # the Port component entity id it links to
  description: "Orchestration — produces silver/gold datasets + every Tier-2 store copy + vectors + lakeFS."
```

**Consumers:**
- `datahub_emit.py` → `emit_applications()` loads it (baked in the image), creates the `datahub_application: true`
  entities via `ApplicationPropertiesClass`, and attaches each dataset/chart/dashboard to its owner via
  `ApplicationsClass` (the app-membership aspect — the direct analog of `DomainsClass` in `emit_domains()`).
- `tofu/port/catalog.tf` → `yamldecode(file("../../config/applications.yaml"))` → sets an `is_data_application`
  property on each component + a relation `datahub_application` to the DataHub Application URN.
- Docs + diagrams → written from it and DoD-checked against it (a component/app in a diagram but not the registry, or
  vice-versa, is drift).

**Ownership is producer-based** and derivable from the existing `emit_*` functions (each already knows what it writes:
`emit_qdrant`/`emit_dbt`/`emit_feast`/… → their owning app). The **one explicit-tag case**: MLflow *experiment traces*
(agent/operator/realm) — the trace URN doesn't reveal which agent produced it, so those attach by an explicit tag, not
a URN rule.

## 4. The roster

### DataHub Applications (owns data now or plausibly will)

| # | App (key) | Group | Owns (producer) |
|---|-----------|-------|-----------------|
| 1 | weyland-dagster | core-producer | silver/gold datasets + all Tier-2 copies (qdrant/weaviate/lancedb/opensearch/duckdb/timescaledb/mysql/clickhouse/cassandra/cockroach/mongo) + lakeFS + vectors |
| 2 | dbt | core-producer | `iceberg.dbt.mart_*` (7 marts) |
| 3 | flink | core-producer | streaming `iceberg analytics.*` |
| 4 | genre-trainer | core-producer | `genre_classifier` model |
| 5 | mlflow | core-producer | registered models / versions / `model_catalog` / experiments |
| 6 | weyland-tool-server | ai-serving | `eval_leaderboard`/`eval_scores`/`eval_runs`, RAG-serving |
| 7 | weyland-agent | ai-serving | `agentic-rag` traces *(explicit tag)* |
| 8 | weyland-operator | ai-serving | `operator_incidents` + traces *(explicit tag)* |
| 9 | realm-of-agents | ai-serving | A2A traces *(explicit tag)* |
| 10 | weyland-guard | ai-serving | `guardrail_verdicts` |
| 11 | feast | data-platform | feature views |
| 12 | cube | data-platform | semantic models over marts |
| 13 | superset | bi | its charts + dashboards (consumer — owns only its BI assets) |
| 14 | lightdash | bi | its charts + dashboards (consumer) |
| 15 | glitchtip | operational | issue/event/span/trace tables |
| 16 | uptime-kuma | operational | monitor/heartbeat tables |
| 17 | keycloak | operational | realm/user/client tables |
| 18 | unleash | operational | feature-flag tables |
| 19 | sonarqube | operational | scan/issue tables |
| 20 | n8n | operational | workflow tables *(verify cataloged)* |
| 21 | woodpecker | operational | CI tables *(verify cataloged)* |
| 22 | ranger | operational | policy/user DB *(verify cataloged)* |
| 23 | open-webui | operational | chat/user DB *(verify cataloged)* |
| 24 | trino | data-platform | `trino.*` federation views |
| 25 | litellm | ai-serving | usage/cost *(future — empty `owns` now)* |
| 26 | bifrost | ai-serving | usage/cost *(future — empty `owns` now)* |

### Port-only (pure compute — never a DataHub Application)

store-scaler (KEDA) · kokoro (TTS) · apisix · mcp-gateway · mcp-compositor · nemo-guardrails · guardrails-structure ·
ray-head (Ray coordinator) · scan-suite (→ Port, not DataHub) · gizmosql/duckdb (query engine).

These still get (or already have) a Port `component` with `is_data_application: false` — so Port stays the complete
inventory, and DataHub holds the data-app subset.

## 5. Per-surface work

1. **Registry** — author `config/applications.yaml` (this taxonomy); bake it into the Dagster image + point Tofu at it.
2. **DataHub** — `emit_applications()` (entities + `ApplicationsClass` attach; explicit-tag path for agent traces) +
   `emit_applications_op` wired into `datahub_catalog_emit_job`. Verify: an Application page in DataHub lists its owned
   assets; an asset's page shows its Application.
3. **Port** — extend `tofu/port/catalog.tf`: `is_data_application` property + `datahub_application` relation on each
   component, driven by the registry. Reconcile any missing `component` entities so Port is complete. (This is the
   "don't lose sight of Port" half.)
4. **Docs** — `arch.md` app-taxonomy section (the two-lens model: Domain = *what business area*, Application = *which
   app owns it*); new `concepts/application-catalog.md`; `api.md`/`tools.md` if surfaced.
5. **Diagrams** — LikeC4 model: apps as elements with data-ownership relations; `platform-map.html` card set reconciled
   1:1 against the registry.
6. **DoD sweep** — the registry is the checklist: every surface diffed against it; a demo (UI walkthrough of a DataHub
   Application page + the Port component link) executed against live infra.

## 6. Open questions / decisions

- **Registry location + delivery** — `config/applications.yaml` at platform root is the proposal; confirm the path is
  both baked into the Dagster build context AND reachable by Tofu at plan time (else a ConfigMap mount + a Tofu
  `local_file` copy).
- **Verify-cataloged operational apps** — n8n / woodpecker / ranger / open-webui: confirm their Postgres schemas are
  actually in the catalog before giving them `owns` patterns; if not yet cataloged, they exist as entities with empty
  `owns` (the "plausibly will" case).
- **DataHub Application ↔ Port component relation direction** — model as a Port relation to the DataHub Application URN
  (Port is the "see" layer that links out), not the reverse.

## 7. DoD

All six pillars + the new cross-surface-taxonomy process (registry = source of truth). Not done until DataHub + Port +
docs + diagrams all agree with `config/applications.yaml`, and the demo is run live.
