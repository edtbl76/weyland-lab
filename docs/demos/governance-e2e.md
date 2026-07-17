# Demo — Governance end-to-end (lineage + DQ verdict + masking on one dataset)

> **Pending live end-to-end validation run.** This stitches three already-authored walkthroughs; the straight-
> through governance arc has **not** yet been executed against live infra.

Follow **one dataset** — the health mart `iceberg.dbt.mart_state_health_trends` — as it visibly accrues all three
L5 governance surfaces in DataHub:

1. **Lineage** — DataHub catalogs the mart with its gold→mart lineage ([catalog-emit.md](catalog-emit.md)).
2. **DQ verdict** — Soda scans the published mart and lands pass/fail as a DataHub Assertion ([soda-dq.md](soda-dq.md)).
3. **Masking policy** — Ranger masks a governed column, provable with a masked-vs-unmasked Trino query
   ([ranger-masking.md](ranger-masking.md)).

This is a **stitch**, not new mechanism — read the three component demos for per-step detail. The point is that
one and the same dataset carries lineage, a quality verdict, and an access policy at once, and all three are
visible from the mart's DataHub page (plus the Trino query for the mask's real-world effect).

**Sequence:** [flow-e2e-governance.md](../diagrams/flow-e2e-governance.md)

## Prerequisites

The union of the three component demos — all must be healthy:

- **The mart exists** — `iceberg.dbt.mart_state_health_trends` (build via [dbt.md](dbt.md) if absent).
- **DataHub** — GMS in-cluster (`datahub-datahub-gms.data-mesh.svc:8080`), UI `datahub.weyland.lab` (Keycloak).
- **Soda** — isolated venv in `deploy/dagster-user-code`; `trino-noauth` proxy up (see [soda-dq.md](soda-dq.md)).
- **Ranger** — Trino native plugin wired, `analyst` user + mask policy applied via `ranger_setup.py` (see
  [ranger-masking.md](ranger-masking.md)).
- `kubectl` runs on **mother** (`emangini@mother`).

## UI walkthrough

1. **Lineage** — open `https://datahub.weyland.lab` → search `mart_state_health_trends` (trino platform) →
   **Lineage** tab. The upstream gold source(s) → mart edges are present (emitted by
   `datahub_catalog_emit_job`, see [catalog-emit.md](catalog-emit.md)).
2. **DQ verdict** — same dataset → **Quality / Validations** tab → the Soda `_NATIVE_` assertions with their
   latest pass/fail (see [soda-dq.md](soda-dq.md)).
3. **Masking** — the Ranger effect is not visible on the DataHub page; prove it with the Trino query in the CLI
   section (masked-vs-unmasked), and view the policy itself at `https://ranger.weyland.lab` → `trino` service →
   Masking tab (see [ranger-masking.md](ranger-masking.md)).

## CLI walkthrough

Kubectl runs on **mother**. Run the three legs in order; each is the headline command from its component demo.

**1 — accrue lineage** (emit the catalog; idempotent upserts):
```
[mother] kubectl -n weyland exec deploy/dagster-user-code -- dagster job execute -j datahub_catalog_emit_job -m weyland_pipeline.definitions
```

**2 — accrue a DQ verdict** (scan + push assertions):
```
[mother] kubectl -n weyland exec deploy/dagster-user-code -- dagster job execute -j soda_quality_job -m weyland_pipeline.definitions
```

**3 — prove the masking policy** (same query, two users):
```
[mother] kubectl -n weyland exec -i deploy/dagster-user-code -- python - <<'PY'
import trino
def q(u):
    c=trino.dbapi.connect(host="trino.data-mesh.svc.cluster.local", port=8080, user=u, catalog="iceberg", schema="dbt")
    cur=c.cursor(); cur.execute("SELECT state, year, depression_pct FROM iceberg.dbt.mart_state_health_trends ORDER BY state LIMIT 3"); return cur.fetchall()
print("analyst (masked):", q("analyst"))
print("dbt (unmasked)  :", q("dbt"))
PY
```

## Expected result

- The **same** `mart_state_health_trends` dataset in DataHub shows **both** a populated **Lineage** tab
  (gold→mart) **and** a populated **Quality** tab (Soda assertions with verdicts).
- The Trino query proves the **access policy** is live: `analyst` sees `depression_pct = None`, `dbt` sees the
  real values — one governed column masked, everything else intact.
- Net: one dataset simultaneously carrying **lineage + a quality verdict + an enforced access policy** — the L5
  governance layer working as a whole, not three disconnected features.

## Cleanup / teardown

All three legs are **non-destructive to the mart**:
- Catalog emit is idempotent upserts — leave in place ([catalog-emit.md](catalog-emit.md)).
- Soda is read-only against the mart; its assertions are idempotent upserts ([soda-dq.md](soda-dq.md)).
- Ranger proof is two read-only SELECTs; the mask policy is the intended steady state ([ranger-masking.md](ranger-masking.md)).

Nothing to tear down. Per-surface removal (soft-delete an assertion, roll back Ranger enforcement) is documented
in each component demo.
