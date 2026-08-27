# The Application Catalog (B82 — the app-centric lens)

**Status:** ✅ **LIVE (2026-08-05).** 29 DataHub **Application** entities + 4,157 assets attached to their owning
app; 54 Port `component` entities flagged + linked. All from one registry. **$0** (OSS / self-hosted).

## Why an app lens

The catalog already answers *"what business area is this?"* (**Domains** — Music, Health, Platform & Ops…) and
*"what bundle does it belong to?"* (**Data Products**). It couldn't answer the operational question you actually ask
at 2am: **"what does app X own / produce / consume?"** — *"what does the `genre-classifier` touch?"*, *"which app
writes `guardrail_verdicts`?"*, *"if I change `weyland-dagster`, what moves?"*

DataHub's **Application** entity is that lens. It sits **alongside** Domains and Data Products — not instead of them:

| Question | Answer via |
|----------|-----------|
| *What business area?* | **Domain** (Music / Health / Platform & Ops …) |
| *What curated bundle?* | **Data Product** (Spotify Audio, Model-Eval Leaderboard …) |
| *Which app owns it?* | **Application** ← this |

A dbt mart, for example, is in the **Music** domain, bundled in the **Spotify Audio** product, and **owned by the
`dbt` Application**. Three orthogonal cuts of the same asset.

## The classification line

An app is a **DataHub Application** iff it **owns cataloged data now, or plausibly will**. Everything else is
**pure compute** — it lives in Port's `component` catalog only (an empty Application entity is noise).

- **Data-plausible → DataHub Application + Port component** (linked). 29 apps: producers (weyland-dagster, dbt, flink,
  genre-trainer, mlflow), AI-serving (tool-server, agent, operator, realm-of-agents, guard), data-platform + BI
  (feast, cube, trino, nessie, lakefs, superset, lightdash), operational-app owners (glitchtip, keycloak, sonarqube,
  unleash, ranger, grafana), and the modeled-now/plausibly-will set (n8n, woodpecker, open-webui, uptime-kuma,
  litellm, bifrost).
- **Pure compute → Port component only.** 25 apps: gateways, stateless serving (whisper, kokoro, llama-guard …),
  UIs, and platform/ops controllers — they own no dataset, so they get a Port component but no Application entity.

**Ownership is producer-based:** each asset attaches to whoever *writes* it (first-match by URN pattern), derived from
the emit functions that already know their outputs. `mart_*` → `dbt`, `guardrail_verdicts` → `weyland-guard`,
`postgres,keycloak.*` → `keycloak`, the Tier-2 store copies → `weyland-dagster` (the broad catch-all, matched last).

## One source of truth, four surfaces

The classification is defined **once** — `weyland_pipeline/applications.yaml` — and every surface consumes or is
DoD-checked against it, so drift is impossible by construction (the DoD's cross-surface-taxonomy process):

- **DataHub** — `emit_applications()` reads the registry → Application entities + `ApplicationsClass` attachment + a
  Documentation link (docs-site), a group **Tag**, and a **Domain** per app.
- **Port** — `tofu/port/applications.tf` reads the *same* file → a `component` per app with `is_data_application` +
  a `datahub_application_url` link-out. 54 components, generated from the registry (not hand-authored).
- **Docs + diagrams** — `arch.md`, this page, the LikeC4 model, and the platform-map are written from + checked
  against the registry. Every deployed Argo app must appear in the registry (component) or its `excluded:` block
  (store / plumbing) — a completeness check with no unaccounted service.

## Where it lives

- **Registry (source of truth):** `services/weyland-dagster/weyland_pipeline/applications.yaml`
- **DataHub emit:** `weyland_pipeline/datahub_emit.py` → `emit_applications()` (in `datahub_catalog_emit_job`)
- **Port:** `tofu/port/applications.tf` + the `component` blueprint props in `catalog.tf`
- **Design + full roster:** `../design/application-taxonomy.md`

## Honest tail

- **Terms** (glossary-term attach per app) is the one enrichment deferred — it needs a real term↔app mapping, worth
  its own pass rather than a rushed guess. Documentation-link, Tags, and Domain are live.
- The **operational "plausibly will" apps** (n8n, woodpecker, open-webui, uptime-kuma, litellm, bifrost) exist as
  Application entities with **no owned assets yet** — their backing stores aren't on `weyland-postgres`. Future assets
  self-attach when cataloged; the entity already exists.
