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

Real schedules (from `weyland_pipeline/schedules` + `definitions.py`):

| Schedule | Job | Cron (America/New_York) | Default |
|---|---|---|---|
| `weyland_ingestion_schedule` | `weyland_ingestion_job` | `17 2 * * *` | RUNNING |
| `weyland_catalog_schedule` | `weyland_catalog_job` | `50 */6 * * *` | RUNNING |
| `datahub_catalog_emit_schedule` | `datahub_catalog_emit_job` | `40 */6 * * *` | RUNNING |
| `weyland_ai_session_schedule` | `weyland_ai_session_job` | `0 */4 * * *` | RUNNING |
| `weyland_timeseries_schedule` | `weyland_timeseries_job` | `25 */4 * * *` | RUNNING |
| `weyland_dbt_schedule` | `weyland_dbt_job` | `0 6 * * 0` | RUNNING |
| `weyland_datasets_music_land_schedule` | `weyland_datasets_music_land_job` | `0 3 * * *` | STOPPED |
| `weyland_datasets_health_land_schedule` | `weyland_datasets_health_land_job` | `0 4 * * *` | STOPPED |

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
4. **API path:** open the launched run in **Runs** to watch it, or launch one from the tool-server
   (below) and follow the returned `run_id` in the Dagster UI.

## CLI walkthrough

Fire a job on demand through the tool-server (the `job_name` enum is
`weyland_ingestion_job` | `weyland_eval_job` | `weyland_eval_score_job`, default the first):

[mother] `curl -s -X POST http://mother:30080/pipeline/trigger -H 'Content-Type: application/json' -d '{"job_name":"weyland_ingestion_job"}'`

Default job (omit the body's job_name):

[mother] `curl -s -X POST http://mother:30080/pipeline/trigger -H 'Content-Type: application/json' -d '{}'`

Launch a job the API enum doesn't cover (e.g. the catalog refresh) from the user-code pod:

[mother] `kubectl -n weyland exec deploy/dagster-user-code -- dagster job execute -j weyland_catalog_job -m weyland_pipeline.definitions`

Confirm the schedule/sensor daemon state:

[mother] `kubectl -n weyland exec deploy/dagster-user-code -- dagster schedule list -m weyland_pipeline.definitions`

[mother] `kubectl -n weyland exec deploy/dagster-user-code -- dagster sensor list -m weyland_pipeline.definitions`

## Expected result

- `/pipeline/trigger` returns `{"status":"ok","run_id":"<uuid>","job_name":"weyland_ingestion_job"}`.
- That `run_id` appears in **Runs** at `dagster.weyland.lab` and proceeds independently.
- `schedule list` / `sensor list` show the RUNNING/STOPPED states from the tables above.

## Cleanup / teardown

Triggering a job launches a **run** — it does not itself create catalog/test artifacts, so there
is nothing to remove for the trigger. The *ingestion* run it starts does write data (RAG stores /
lakeFS); those flows have their own cleanup. If you enabled `datasets_music_raw_sensor` for the
demo, **toggle it back to STOPPED** in the Dagster UI (its default) so it does not fire on the next
raw write.
