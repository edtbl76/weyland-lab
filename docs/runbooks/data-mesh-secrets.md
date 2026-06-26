# Data-mesh secrets — shapes, regeneration, and escrow

Interim record until SealedSecrets/External-Secrets lands (**B69**). These secrets are created
imperatively (`kubectl create secret …`) and are **not** restored by git — so a cluster rebuild
needs this page. Example *shapes* are committed (`k8s/data-mesh/*-secret.example.yaml`); the
*values* are not. Most can be regenerated; **one cannot** — see the ⚠️ below.

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
