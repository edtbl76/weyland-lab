# Flow — Soda data-quality scan → DataHub Assertions (E2E)

Soda Core runs an **independent contract scan** over the 7 dbt marts (`iceberg.dbt.mart_*`) — row presence, key
uniqueness/completeness, value-range bounds, and per-column **emptiness tripwires** — then pushes each check to
**DataHub as a `_NATIVE_` DATASET Assertion** on the mart's `trino` URN. It is Slice C of the L5
(Governance/Security) layer (Ranger + OPA + Soda), complementary to dbt's in-transform tests: dbt validates
*during* the build (row-level, null-filtered); Soda validates the *published output* (aggregate) and so catches
all-NULL columns that dbt range checks pass vacuously. Soda lives in an isolated venv (`/opt/soda-venv`) inside
the `dagster-user-code` image and shells out; its Trino connector sends HTTP Basic auth, which Trino checks since
B233 (2026-10-23): it logs in as `dbt` over HTTPS on 8443 (`REQUESTS_CA_BUNDLE` = the lab CA for the subprocess only).
Before B233 it went through the `trino-noauth` proxy, which stripped `Authorization`. The `-srf` scan-results
JSON is the venv↔main-env bridge that `emit_soda_assertions` reads back. There is no Soda web UI (Soda Cloud is
paid, $0 rule); results land in Dagster run logs and each mart's DataHub Quality tab. See
[../demos/soda-dq.md](../demos/soda-dq.md) and [../runbooks/soda.md](../runbooks/soda.md).

## Sequence

```mermaid
sequenceDiagram
    actor User
    participant Dag as Dagster soda_quality_job
    participant Soda as Soda venv (/opt/soda-venv, subprocess)
    participant Trino as Trino
    participant Marts as iceberg.dbt.mart_*
    participant Emit as emit_soda_assertions
    participant DH as DataHub GMS

    User->>Dag: launch soda_quality_job
    Dag->>Soda: soda scan -d weyland -srf results.json
    Soda->>Trino: SodaCL checks (HTTPS 8443, login dbt)
    Trino->>Marts: aggregate checks (row count, uniqueness, ranges, missing_percent)
    Marts-->>Soda: pass/fail per check
    Soda-->>Dag: -srf scan-results JSON (venv ↔ main-env bridge)
    Dag->>Emit: read results JSON
    Emit->>DH: upsert _NATIVE_ assertion (md5(table:check)) + AssertionRunEvent
    DH-->>User: mart → Quality tab shows pass/fail
```

Assertions are stable, idempotent upserts (URN = `md5(table:check)`), so re-runs update the same records — they
are the governance record, normally left in place. The emptiness tripwire (`missing_percent(<col>) < 100`) fails
loudly on an all-NULL column, the class of bug it caught in `mart_country_health` (the WHO GHO code-vs-label bug
that nulled 7 columns).
