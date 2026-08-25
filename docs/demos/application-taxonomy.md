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

**Port side** — the component entities. **Corrected 2026-08-25 (B137):** `tofu plan` is the WRONG check here and
was always misleading — component entities are **not** in OpenTofu. B60 split schema (tofu) from data (MCP + the
integrations), and until B137 executed the `state rm` half, those 64 entities sat in state making every plan report
`0 to add, 64 to change`. Ask Port directly instead:

```
cd nodes/mother/lab/weyland-platform/tofu/port && set -a && . ./.env && set +a && TOK=$(curl -sS -X POST https://api.port.io/v1/auth/access_token -H 'Content-Type: application/json' -d "{\"clientId\":\"$PORT_CLIENT_ID\",\"clientSecret\":\"$PORT_CLIENT_SECRET\"}" | python3 -c 'import sys,json;print(json.load(sys.stdin)["accessToken"])') && curl -sS https://api.port.io/v1/blueprints/component/entities -H "Authorization: Bearer $TOK" | python3 -c "
import sys,json,collections
e=json.load(sys.stdin)['entities']
print('components:',len(e))
print('is_data_application:',dict(collections.Counter(x['properties'].get('is_data_application') for x in e)))"
```

Expected: **64 components**. For the tofu lane's own coverage check see
[port-iac-coverage.md](port-iac-coverage.md).

**Drift guard** — every deployed Argo app is accounted for in the registry:
```
bash scripts/check-app-registry.sh
```
Expected: `✅ every deployed Argo app is accounted for in the registry` (77 apps).

## Teardown

Read-only demo — nothing to tear down. Re-running `emit_applications()` is idempotent (DataHub upserts); the Port
`for_each` is declarative. To *remove* the lens you'd delete the Application entities + `tofu destroy` the components,
but that's not part of the demo.
