# Demo — Dagster health and "why did a run fail?" (B239)

The read-only diagnostic in [runbooks/dagster.md](../runbooks/dagster.md), run against the live instance on
2026-11-08. Flow: [diagrams/flow-dagster-runs.md](../diagrams/flow-dagster-runs.md).

## CLI walkthrough

**1. Health.**

[rogueone]
```bash
kubectl exec -i -n weyland deploy/dagster-user-code -- python3 - --health < /home/edwardmangini/IdeaProjects/weyland/scripts/lib/dagster_runs.py
```

Seen: seven daemons healthy (SENSOR, BACKFILL, SCHEDULER, QUEUED_RUN_COORDINATOR, MONITORING, ASSET,
FRESHNESS_DAEMON), `code location weyland_pipeline: LOADED`, `OK`, exit 0.

**2. Recent failures and why.**

[rogueone]
```bash
kubectl exec -i -n weyland deploy/dagster-user-code -- python3 - --job datahub_catalog_emit_job --limit 3 < /home/edwardmangini/IdeaProjects/weyland/scripts/lib/dagster_runs.py
```

Seen: three nightly failures (2026-11-06, -07, -08, all 05:35 UTC), and for the newest
`run failed: Exceeded maximum runtime of 1800 seconds.` with `step failed: emit_tag_assignments_op`. Asking about
the 11-07 run by id (`--run e1185e87-d4b8-4cbf-8bff-dad12e924cde`) showed the same limit hit in a different step
(`emit_source_terms_op`). That is a real problem the demo found: the job has failed every night since at least
2026-11-04, its last success more than 9 days old (B239 finding 15).

`--job weyland_dbt_job` explained the job's older failures (latest 2026-10-18) with the actual dbt error
(`20 of 66 ERROR unique_mart_fma_genre_tree_genre_id …`).

**3. Negative cases.**
- A job with no failures: `--job linear_digest_job` printed `no failed runs for linear_digest_job among the most
  recent 5`, exit 1.
- Refused input: `--job 'bad name'` printed `job name 'bad name' must be letters, digits and underscores`, exit 2.
  Nothing reached Dagster.

**4. `lab-ask` now answers.** `lab-commands why did a run fail` lists this runbook's commands; before B239 the
question was "not in the index".

## UI walkthrough

<https://dagster.weyland.lab> → Runs → Status: Failure → open a `datahub_catalog_emit_job` run: the failed step and
the "Exceeded maximum runtime" message match the CLI output. Deployment → Daemons shows the same seven healthy daemons.

## Cleanup

None: every call is a GraphQL query. Nothing is launched, written or changed.
