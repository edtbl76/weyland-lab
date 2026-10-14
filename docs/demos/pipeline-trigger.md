# Demo — Pipeline Trigger (Dagster schedules + sensors)

Dagster jobs in the weyland pipeline fire three ways: on a **schedule** (cron), from a **sensor**
(event-driven, e.g. a new raw file lands in lakeFS/MinIO), or **on demand** via the tool-server
`/pipeline/trigger` API (a `launchRun` GraphQL mutation). This demo shows all three. The
`/pipeline/trigger` launch mechanism has its own sequence diagram — see
[../diagrams/flow-pipeline-trigger.md](../diagrams/flow-pipeline-trigger.md).

## Sequence diagram

Reuse the existing diagram: **[../diagrams/flow-pipeline-trigger.md](../diagrams/flow-pipeline-trigger.md)**
(`/pipeline/trigger` → tool-server → Dagster `launchRun` → run id back). The schedule/sensor paths
are the same `launchRun`, fired by the Dagster daemon instead of an API caller.

## Prerequisites

- `mother` — hosts Dagster (webserver + daemon + `dagster-user-code`) and the tool-server.
- Dagster UI at `dagster.weyland.lab` (Keycloak SSO); tool-server at `http://mother:30080`
  (NodePort; `/docs`, `/openapi.json`).
- Login: `emangini` / `weyland_dev_password`.

Schedules: the live set, times and RUNNING/STOPPED state are in **[../schedules.md](../schedules.md)** (the single
source of truth for every timer; `definitions.py` holds the code). This page used to copy that table and drifted
(it still showed the 6-hourly catalog emit, daily since 2026-08-07), so it points there instead.

Real sensors (`weyland_pipeline/sensors`, `lancedb_sync`):

- `datasets_music_raw_sensor` — polls MinIO `datasets/music/raw/` every 60s; on a new `.csv`
  (cursor = newest object timestamp) fires `weyland_datasets_music_transform_job`. Default STOPPED.
- `lancedb_sync_sensor` — fires `weyland_lancedb_sync_job` on a LanceDB load.

## UI walkthrough

1. Open `https://dagster.weyland.lab` → **Automation**. You see the schedules + sensors above with
   their RUNNING/STOPPED state and next tick.
2. **Schedule path:** open a RUNNING schedule (e.g. `weyland_catalog_schedule`), click
   **Test Schedule** / **Preview** to see the run it would launch, or **Materialize / Launch** the
   underlying job (`weyland_catalog_job`) directly.
3. **Sensor path:** open `datasets_music_raw_sensor`. It is STOPPED by default — toggle it on, then
   use **Test Sensor** to evaluate the cursor against MinIO. Dropping a new CSV under
   `datasets/music/raw/` produces a `RunRequest` for `weyland_datasets_music_transform_job`.
4. **API path:** open the launched run in **Runs** to watch it, or launch one with `launchRun` (below) or through
   the operator, and follow the returned run id in the Dagster UI.

## CLI walkthrough

**On demand through the tool-server is an ACT, and acts are guarded** (B14 `act` hook, enforced since B207,
2026-10-14). Only the MCP gateway's identity may reach `/pipeline/trigger` (Istio), and the actor it forwards must be on
`policy.gate`'s allowlist (`weyland-operator`). So the operator path is the supported way to trigger through the API: ask
the operator in Telegram ("run the ingestion job") and confirm. A direct call from the LAN is refused by the mesh, which is
the expected result and the negative case:

`curl -s -o /dev/null -w '%{http_code}\n' -X POST http://mother:30080/pipeline/trigger -H 'Content-Type: application/json' -d '{"job_name":"weyland_ingestion_job"}'`
→ `403` (body `RBAC: access denied`).

The guard's own refusal (an actor not on the allowlist) is the drill in [act-guard.md](act-guard.md).

Launch any job directly through the Dagster API, recorded in **Runs** (the documented form; `dagster job execute` in a pod
runs ephemerally and is never recorded):

```
kubectl exec -n weyland deploy/dagster-user-code -c dagster-user-code -- python3 -c "import json,urllib.request;q='mutation(\$p:ExecutionParams!){launchRun(executionParams:\$p){__typename ... on LaunchRunSuccess{run{runId}} ... on PythonError{message}}}';v={'p':{'selector':{'repositoryLocationName':'weyland_pipeline','repositoryName':'__repository__','jobName':'weyland_catalog_job'},'runConfigData':{}}};r=urllib.request.Request('http://dagster-webserver.weyland.svc.cluster.local:3000/graphql',data=json.dumps({'query':q,'variables':v}).encode(),headers={'Content-Type':'application/json'});print(json.load(urllib.request.urlopen(r))['data']['launchRun'])"
```

Confirm the schedule/sensor daemon state:

`kubectl -n weyland exec deploy/dagster-user-code -- dagster schedule list -m weyland_pipeline.definitions`

## Expected result

- The direct LAN call returns `403` (`RBAC: access denied`). Through the operator, `/pipeline/trigger` returns
  `{"status":"ok","run_id":"<uuid>","job_name":"weyland_ingestion_job"}`.
- `launchRun` prints `{'__typename': 'LaunchRunSuccess', 'run': {'runId': '<uuid>'}}`.
- That `run_id` appears in **Runs** at `dagster.weyland.lab` and proceeds independently.
- `schedule list` / `sensor list` show the RUNNING/STOPPED states listed in schedules.md.

## Cleanup / teardown

Triggering a job launches a **run** — it does not itself create catalog/test artifacts, so there
is nothing to remove for the trigger. The *ingestion* run it starts does write data (RAG stores /
lakeFS); those flows have their own cleanup. If you enabled `datasets_music_raw_sensor` for the
demo, **toggle it back to STOPPED** in the Dagster UI (its default) so it does not fire on the next
raw write.
