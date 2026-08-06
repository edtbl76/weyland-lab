# Flow — Great Expectations auto-profiling → DataHub Assertions + Data Docs (B77 part b)

Great Expectations is the **profiling showcase** of the data-quality layer (part b) — on-demand, ~$0 standing RAM.
The `ge_validate_job` shells out to the isolated `/opt/ge-venv` (GE **0.18**, pinned because acryl-datahub 1.7 dropped
the native GE action). Per showcase table it opens a **Fluent Trino *table* asset** (user `dbt` via the `trino-noauth`
proxy), lets the **`UserConfigurableProfiler`** auto-generate a per-column suite (types, non-null, min/max/quantile
ranges, value sets, uniqueness — GE's actual differentiator), validates it with a checkpoint, and builds **Data
Docs**. The main-env `emit_ge_assertions` reads the validation-results JSON and hand-rolls each expectation into a
DataHub Assertion (nativeType = expectation type, column-scoped when it targets a column) — so GE lands **alongside
Soda and the `@asset_check` gate** on the same dataset's Quality tab (one pane, three sources). Data Docs write to the
`ge-data-docs` PVC (the run executes *in* the user-code pod via `DefaultRunLauncher`) and the `ge-docs` nginx serves
them at `ge-docs.weyland.lab`. The auto-profiler sets tight bounds, so some checkpoints fail on the same data —
expected, **advisory** (the op exits 0, never fails the job). See [../demos/great-expectations.md](../demos/great-expectations.md).

```mermaid
sequenceDiagram
  autonumber
  actor U as Operator (Dagster UI)
  participant OP as ge_validate_op (user-code pod)
  participant GE as /opt/ge-venv (GE 0.18)
  participant TR as Trino (trino-noauth, user dbt)
  participant PVC as ge-data-docs PVC
  participant EM as emit_ge_assertions (main env)
  participant DH as DataHub GMS
  participant NG as ge-docs nginx

  U->>OP: launch ge_validate_job
  OP->>GE: subprocess ge_validate.py
  loop each showcase table (marts + a silver)
    GE->>TR: table asset + UserConfigurableProfiler (aggregate metric queries)
    TR-->>GE: column stats
    GE->>GE: build suite -> checkpoint validate
    GE->>PVC: build Data Docs (gx/uncommitted/data_docs/local_site)
  end
  GE-->>OP: /tmp/ge_results.json + exit 0 (advisory)
  OP->>EM: emit_ge_assertions(results)
  EM->>DH: AssertionInfo + RunEvent per expectation (339)
  NG-->>U: ge-docs.weyland.lab serves the PVC (Keycloak SSO)
  DH-->>U: GE assertions on each dataset Quality tab (with Soda + @asset_check)
```
