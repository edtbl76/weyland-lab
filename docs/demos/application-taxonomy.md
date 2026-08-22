# Demo — Application taxonomy (B82)

The app-centric catalog lens: **which app owns / produces / consumes an asset**, alongside Domains and Data Products.
One registry drives DataHub Applications + Port components. **Executed + eyes-on 2026-08-05** (✅).

- **Concept:** [concepts/application-catalog.md](../concepts/application-catalog.md) · **arch:** §7f · **design:** `aidlc-docs/application-taxonomy.md`
- **Flow:** [diagrams/flow-application-taxonomy.md](../diagrams/flow-application-taxonomy.md)

## UI walkthrough (eyes-on)

1. **DataHub → an Application** — `https://datahub.weyland.lab` → Browse → **Applications** → `weyland-dagster`.
   **UAT — confirm:**
   - **Owned Assets** is populated (the silver datasets + every Tier-2 store copy) — not empty.
   - **Documentation** tab shows a "Docs — Weyland Dagster" link resolving to `https://docs.weyland.lab/runbooks/datasets-hydration/` (has the `/` — the v18 fix).
   - **Properties** shows `group`, `key`, `owns_patterns`.
   - **Domain** + a group **Tag** are set; **Glossary Terms** shows the capabilities (Orchestration · Data Production · Catalog & Governance).
2. **DataHub → a dataset's app** — open a `mart_*` dataset → its **Application** is `dbt` (owned by the transform, not the pipeline).
3. **DataHub → Browse → Glossary → Application Capabilities** — the 30-term vocabulary (LLM Gateway, Retrieval / RAG, Guardrails, …).
4. **Port → a component** — `https://app.port.io` → Catalog → **Components** → `bifrost` → **Data Application = false** (pure compute), and `weyland-guard` → **true** with a **DataHub Application** link-out. 54 components total.

## CLI walkthrough (the test — RUN against live infra)

**Emit + verify the DataHub side** — 29 entities, N assets attached:
```
kubectl -n weyland exec deploy/dagster-user-code -- python -c "import weyland_pipeline.datahub_emit as d; print(d.emit_applications())"
```
Expected: `(29, 4157)`, then `APP ATTACHMENT: {...}` + `ZERO-ASSET APPS: [...]` (the empty ones are the plausibly-will / no-source apps — expected).

**Port side** — 54 components with the flag distribution:
```
tofu -chdir=tofu/port plan   # clean (no drift) once applied
```

**Drift guard** — every deployed Argo app is accounted for in the registry:
```
bash scripts/check-app-registry.sh
```
Expected: `✅ every deployed Argo app is accounted for in the registry` (79 apps).

## Teardown

Read-only demo — nothing to tear down. Re-running `emit_applications()` is idempotent (DataHub upserts); the Port
`for_each` is declarative. To *remove* the lens you'd delete the Application entities + `tofu destroy` the components,
but that's not part of the demo.
