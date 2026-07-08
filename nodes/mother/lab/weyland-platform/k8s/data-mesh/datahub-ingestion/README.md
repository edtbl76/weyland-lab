# DataHub managed-ingestion recipes (source-of-record)

DataHub's UI-configured managed-ingestion sources live in GMS (Postgres-backed), not in git —
so they don't survive a DataHub rebuild and weren't reproducible. These recipe YAMLs are the
**committed source-of-record**: if DataHub is rebuilt, recreate each UI source by pasting the
matching recipe (Ingestion → Sources → Create → paste recipe) and re-creating its DataHub
Secret(s). Tokens/creds are **placeholders** (`${...}`) here — never commit the real values;
they live as DataHub Secrets (Ingestion → Secrets), and the underlying k8s secrets should move
to SealedSecrets/External-Secrets under B69.

| Source | Recipe | Schedule | Secrets (DataHub) |
|---|---|---|---|
| Iceberg (Nessie REST + MinIO) | `iceberg.recipe.yaml` | daily | `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` |
| Grafana (in-cluster) | `grafana.recipe.yaml` | 02:00 daily | `GRAFANA_SA_TOKEN` |
| dbt (transform tier) | `dbt.recipe.yaml` | daily | `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` (reads `s3://warehouse/_dbt_artifacts/`) |

Connectivity note: every source points at the **in-cluster service** (not the forward-auth
`*.weyland.lab` ingress, which 401s API calls). The DataHub executor is meshed/PERMISSIVE so
it reaches in-cluster services; STRICT-mTLS targets still connect.
