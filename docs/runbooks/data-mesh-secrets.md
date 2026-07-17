# Data-mesh secrets — shapes, regeneration, and escrow

**SealedSecrets landed in B69** — these secrets are now sealed into git and restored by Argo. See
[secrets.md](secrets.md) for the sealing/restore/rotation *mechanism*; this page remains the reference for the
**shapes** of each secret and how to **regenerate individual values** (still needed when rotating a credential or
reconstructing one from its source system). Most values can be regenerated; the ⚠️ ones cannot and are also
raw-escrowed off-cluster.

| Secret (ns) | Keys | Regenerate? | How |
|---|---|---|---|
| `nessie-secret` (data-mesh) | `postgres-password`, `s3-access-key`, `s3-secret-key` | yes | PG: reset the `nessie` role pw + update; S3: MinIO access keys for the warehouse bucket |
| `lakefs-secret` (data-mesh) | `database-connection-string`, `s3-access-key`, `s3-secret-key`, **`encrypt-key`** | **NO** for `encrypt-key** | DSN/S3 regenerable; ⚠️ `encrypt-key` is **NOT** |
| `iceberg-s3-secret` (weyland) | `access_key`, `secret_key` | yes | mirror of `nessie-secret` S3 creds (see iceberg_publish.py / user-code.yaml) |
| `datahub-token` (weyland) | `token` | yes | DataHub UI → Settings → Access Tokens (admin) → regenerate; `read -rs` into the secret |
| `datahub-auth-secrets` (data-mesh) | system-client id/secret | yes | fixed values; provisionSecrets.enabled=false so they don't churn |
| `datahub-oidc` (data-mesh) | `AUTH_OIDC_CLIENT_SECRET` | yes | Keycloak `datahub` client secret (tofu/keycloak) |
| `minio-creds` (minio) | `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` | risky | regenerating root creds requires re-keying every S3 client |
| Grafana SA token (DataHub Secret) | `GRAFANA_SA_TOKEN` | yes | mint via the Grafana admin API (`grafana-admin` secret → `POST /api/serviceaccounts` → `/tokens`) |

## ⚠️ lakeFS `encrypt-key` — escrow this NOW

`lakefs-secret/encrypt-key` (`LAKEFS_AUTH_ENCRYPT_SECRET_KEY`) is the key lakeFS uses to encrypt
its **stored credentials and auth data in Postgres**. If it's lost, **every credential lakeFS has
stored becomes undecryptable** — the install is effectively bricked even with a Postgres backup.
It is **not** regenerable.

**Action (do once):** copy the live value somewhere durable and off-cluster —
```
kubectl -n data-mesh get secret lakefs-secret -o jsonpath='{.data.encrypt-key}' | base64 -d
```
— into a password manager. The pg/MinIO backup CronJobs back up the *data*, not k8s secrets, so this
key is not otherwise protected until B69 (SealedSecrets) puts the secret shape (sealed) in git.

## DataHub ingestion secrets — durable via pod ENV (not UI Secrets)

**Problem:** DataHub UI-entered Secrets live in the GMS metadata store — **any GMS/system-DB reset wipes them**,
and every secret-backed managed-ingestion source then fails at once (`connection … no password supplied`,
`requires authentication`). The tell: postgres/neo4j/grafana/mongo all red while trino/mlflow (no secret refs)
stay green.

**Durable fix:** recipe `${VAR}` refs resolve from the **`acryl-datahub-actions` pod ENV** (ingestion runs as
its subprocess), not only UI Secrets. So inject the creds as `extraEnvs` (`secretKeyRef`, `optional: true`) on
`acryl-datahub-actions` in `k8s/data-mesh/datahub-values.yaml`, from a k8s Secret
**`data-mesh/datahub-ingestion-secrets`** (created out-of-band — a k8s object survives GMS resets). Keys:
`WEYLAND_PG_PASSWORD` / `NEO4J_PASSWORD` / `MONGO_PASSWORD` (all = `weyland_dev_password`) + `GRAFANA_SA_TOKEN` +
`MINIO_ACCESS_KEY`/`MINIO_SECRET_KEY`. The `.recipe.yaml` files in `k8s/data-mesh/datahub-ingestion/` are the
source-of-record → after a wipe, re-paste the recipe into the UI source and creds auto-resolve from env, **no
secret re-entry**.

```
kubectl -n data-mesh create secret generic datahub-ingestion-secrets \
  --from-literal=WEYLAND_PG_PASSWORD='weyland_dev_password' \
  --from-literal=NEO4J_PASSWORD='weyland_dev_password' \
  --from-literal=MONGO_PASSWORD='weyland_dev_password' \
  --from-literal=GRAFANA_SA_TOKEN='<glsa_…>' \
  --dry-run=client -o yaml | kubectl apply -f -
```

**Gotchas:** ① **Mongo** — the DataHub mongodb source needs creds IN the connect_uri
(`mongodb://weyland:${MONGO_PASSWORD}@mongodb.data-mesh.svc.cluster.local:27017/?authSource=admin`), and you must
**edit the live UI source** — re-running ≠ applying the recipe file. ② **Grafana** — the SA token is shown once
and unrecoverable; SSO hides the UI token page, so mint via the local-admin API in a throwaway curl pod
(`grafana-admin` secret → `POST /api/serviceaccounts` → `/tokens`). ③ verify with
`kubectl -n data-mesh exec deploy/datahub-acryl-datahub-actions -- printenv WEYLAND_PG_PASSWORD NEO4J_PASSWORD MONGO_PASSWORD GRAFANA_SA_TOKEN`.
