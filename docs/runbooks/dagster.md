# Dagster — runbook

Dagster runs the lab's scheduled data work: ingestion, the dataset land and hydrate jobs, dbt, the DataHub catalog
emit, the evals, the Linear backup and digest, and more (the full list is in `docs/schedules.md`). UI:
<https://dagster.weyland.lab> (Keycloak forward-auth). Written by B239 (2026-11-08), which found that no runbook
covered operating it.

## How it is built

| Part | Deployment (ns `weyland`) | What it does |
|---|---|---|
| Webserver | `dagster-webserver` | the UI and the GraphQL API at `dagster-webserver.weyland.svc.cluster.local:3000/graphql` |
| Daemon | `dagster-daemon` | schedules, sensors, the run queue, run monitoring (max runtime) |
| User code | `dagster-user-code` | the gRPC code server for `weyland_pipeline`, **and where every run executes** |

- **Runs execute inside the user-code pod** (`DefaultRunLauncher`), not in pods of their own. A run that runs out of
  memory can take the code server down with it, and its logs are that pod's logs.
- **One run at a time** (`QueuedRunCoordinator`, concurrency 1): two heavy runs at once exhausted the pod. Others
  wait in the queue.
- **Max runtime:** 4 h for the instance (`run_monitoring.max_runtime_seconds` in `k8s/dagster/configmap.yaml`), and a
  per-job `dagster/max_runtime` tag in `services/weyland-dagster/weyland_pipeline/definitions.py`: 1800 (30 min) for
  `ge_validate_job` and `feast_materialize_job`, 4200 (70 min) for `datahub_catalog_emit_job` (raised from 1800 by
  B239, 2026-11-08, after it outgrew the cap; `tests/test_job_runtime_limits.py` keeps the cap at 2x its measured
  runtime). A run over its limit is stopped and fails with "Exceeded maximum runtime". A launched run can carry its
  own `dagster/max_runtime` tag, which overrides the job's for that run.
- Code: `services/weyland-dagster/weyland_pipeline/` (`definitions.py` registers the jobs, `schedules/` the
  schedules). Image shipped with `scripts/ship-images.sh` ([ship-images.md](ship-images.md)).

## Is it healthy?

```bash
kubectl -n weyland get deploy dagster-webserver dagster-daemon dagster-user-code
```

All three should be `1/1`. Then ask Dagster itself whether the daemons are heartbeating and the code loaded:

[rogueone]
```bash
kubectl exec -i -n weyland deploy/dagster-user-code -- python3 - --health < /home/edwardmangini/IdeaProjects/weyland/scripts/lib/dagster_runs.py
```

Expected: seven `daemon …: healthy` lines, `code location weyland_pipeline: LOADED`, then `OK` (exit 0). An
unhealthy required daemon or a code location that failed to load prints `UNHEALTHY` and exits 1. UI: Deployment →
Daemons, and Deployment → Code locations.

## Why did a run fail?

In the UI: **Runs**, filter Status = Failure, open the run. The failed step is red; its error and the compute logs
(stdout/stderr) are in the step's log pane.

From the command line, the most recent failed runs and why the newest one failed:

[rogueone]
```bash
kubectl exec -i -n weyland deploy/dagster-user-code -- python3 - < /home/edwardmangini/IdeaProjects/weyland/scripts/lib/dagster_runs.py
```

One job only (`--limit` sets how many runs to list, default 5):

[rogueone]
```bash
kubectl exec -i -n weyland deploy/dagster-user-code -- python3 - --job datahub_catalog_emit_job --limit 3 < /home/edwardmangini/IdeaProjects/weyland/scripts/lib/dagster_runs.py
```

A specific run, by the full id from the list:

[rogueone]
```bash
kubectl exec -i -n weyland deploy/dagster-user-code -- python3 - --run 6a6f3d61-f0be-4d2f-ab89-87f6fb37701c < /home/edwardmangini/IdeaProjects/weyland/scripts/lib/dagster_runs.py
```

It prints each failed step's error and the run's failure message, in event order, for example:

```text
why 6a6f3d61-f0be-4d2f-ab89-87f6fb37701c (datahub_catalog_emit_job, FAILURE) failed:
  run failed: Exceeded maximum runtime of 1800 seconds.
  step failed: emit_tag_assignments_op: dagster._core.errors.DagsterExecutionInterruptedError
```

Exit 0 when it explained a run, 1 when there are no failed runs to explain, 2 when it could not ask Dagster or the
input was refused. It only queries; it never launches or changes anything.

**What the common messages mean:**

| Message | Meaning | Next step |
|---|---|---|
| `Exceeded maximum runtime of N seconds` | the run hit its max runtime and was stopped; the interrupted step varies | find why it got slower (data growth, a slow upstream); raise the job's `dagster/max_runtime` tag only with a reason |
| `DagsterDbtCliRuntimeError … failed with exit code 1` | a dbt model or test failed | the message lists the failing tests; the full dbt log path is in it ([dbt.md](dbt.md)) |
| `no failure event recorded` | the process died from outside (out of memory, eviction) | the user-code pod logs and events, below |

## Logs

The runs' output is the user-code pod's output:

```bash
kubectl -n weyland logs deploy/dagster-user-code --tail=200
```

After a crash, the previous container's logs and the reason it restarted:

```bash
kubectl -n weyland logs deploy/dagster-user-code --previous --tail=200; kubectl -n weyland get pods | grep dagster-user-code; kubectl -n weyland describe pod -l app=dagster-user-code | grep -A3 -iE 'last state|reason'
```

Schedules, sensors and the run queue are the daemon's:

```bash
kubectl -n weyland logs deploy/dagster-daemon --tail=200
```

## Run a job now

Launch through Dagster, so the run is recorded in the run database and counts for the freshness watchdog: in the UI,
Jobs → the job → Launchpad → Launch run. From the command line, the same GraphQL `launchRun` the other runbooks use;
replace `linear_backup_job` with the job's name:

```bash
kubectl exec -n weyland deploy/dagster-user-code -- python3 -c "import json,urllib.request;q='mutation(\$p:ExecutionParams'+chr(33)+'){launchRun(executionParams:\$p){__typename ... on LaunchRunSuccess{run{runId}} ... on PythonError{message}}}';v={'p':{'selector':{'repositoryLocationName':'weyland_pipeline','repositoryName':'__repository__','jobName':'linear_backup_job'},'runConfigData':{}}};r=urllib.request.Request('http://dagster-webserver.weyland.svc.cluster.local:3000/graphql',data=json.dumps({'query':q,'variables':v}).encode(),headers={'Content-Type':'application/json'});print(json.load(urllib.request.urlopen(r))['data']['launchRun'])"
```

Expected: `{'__typename': 'LaunchRunSuccess', 'run': {'runId': '…'}}`. Then follow it with the diagnostic above or
in the UI.

**Do not use `dagster job execute` through `kubectl exec` for a run that must count.** The pod has no
`DAGSTER_HOME`, so the CLI runs on a throwaway in-memory instance. The side effects are real, but the run never
reaches the run database, so the watchdog neither sees it nor clears its alert. Use the CLI only to test side
effects.

## Restart

```bash
kubectl -n weyland rollout restart deployment/dagster-user-code deployment/dagster-webserver deployment/dagster-daemon
```

Restarting `dagster-user-code` **stops any run in progress** (runs execute in that pod; it deploys `Recreate`).
Check Runs for anything in progress first. A run stopped this way shows as failed and is not resumed
(`max_resume_run_attempts: 0`); launch it again after the restart.

## Watchdog and alerts

`dagster-freshness-check` (a CronJob) checks every scheduled job's latest run against a budget in
`k8s/dagster/freshness.yaml`. It fires `DagsterJobFailed` (the last run failed), `DagsterJobStale` (no success within
the budget) and `DagsterJobNeverRan`, all at **warning** severity. Warnings do not open a Linear incident (U14 files
critical alerts only), so a failing job can stay failing until someone reads the warning. Details and how to run
the check now: [observability.md § Dagster job watchdog](observability.md#dagster-job-watchdog--budgets-and-the-guard-b94-b196-2026-09-27).

## Related

- Schedules and their times: `docs/schedules.md`.
- Per-job operations: [linear-backup.md](linear-backup.md), [dbt.md](dbt.md), [datahub.md](datahub.md),
  [great-expectations.md](great-expectations.md), [datasets-hydration.md](datasets-hydration.md).
- Restore: Dagster's run and event history lives in the core Postgres database; see `docs/dr.md`.
