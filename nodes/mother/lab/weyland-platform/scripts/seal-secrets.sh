#!/usr/bin/env bash
# B69 Wave 2 — seal the IMPERATIVE cluster secrets into git-safe SealedSecret CRs.
# Run on MOTHER (needs kubectl cluster access + kubeseal + the sealed-secrets controller in kube-system).
#
#   ./seal-secrets.sh            # DRY RUN — validates each allow-list entry exists (flags typos as MISSING)
#   ./seal-secrets.sh --seal     # annotate-managed + seal each -> writes CRs to $OUT
#
# Then: rsync "$OUT"/  ->  repo k8s/sealed-secrets/sealed/ , commit + push -> Argo applies them.
# The controller adopts the EXISTING secret (via the `sealedsecrets.bitnami.com/managed` annotation we add) and
# reconciles it to the sealed value — identical to the live value, so nothing is disrupted.
#
# EXPLICIT ALLOW-LIST (curated from the full cluster inventory 2026-07-17). We seal ONLY secrets created
# IMPERATIVELY — nothing else recreates them, so they must live in git to be restorable. We deliberately DO NOT
# seal:
#   - operator-owned / operator-rotated secrets: all prometheus-operator + alertmanager-*/prometheus-* secrets,
#     monitoring-kube-prometheus-admission, gatekeeper-webhook-server-cert (rotating webhook certs).
#   - Helm/chart-generated secrets (the chart recreates them on install, so no sealing needed): datahub-gms-secret,
#     datahub-auth-secrets, datahub-encryption-secrets, datahub-secret, superset-config, superset-env,
#     lightdash / lightdash-secret, jupyterhub `hub`, prerequisites-kafka-*.
#   - TLS/CA: weyland-wildcard-tls, weyland-mkcert-ca — mkcert-regenerable, replicated across namespaces, expire.
# (Revisit the chart-generated DataHub/Superset secrets only if PATs/signing keys must survive a full rebuild.)
set -euo pipefail
OUT="${OUT:-$HOME/sealed-out}"
SEAL=0; [ "${1:-}" = "--seal" ] && SEAL=1

SECRETS=(
  # --- weyland (28) ---
  weyland/aidlc-kb-minio-secret
  weyland/apisix-secret
  weyland/cosign-signing-key         # B88 — cosign image-signing key. ⚠ BRICKING: lose it and every
                                     # image already signed can no longer be verified against the
                                     # public key shipped in k8s/gatekeeper/image-signatures.yaml.
                                     # Escrow off-cluster like glitchtip-secret.
  weyland/cron-freshness-woodpecker  # B135 — Woodpecker API token for the scheduled-work watchdog
  weyland/dagster-postgres-secret
  weyland/dagster-sentry
  weyland/datahub-token
  weyland/glitchtip-secret            # ⚠ bricking: Django SECRET_KEY — also escrow off-cluster
  weyland/iceberg-s3-secret
  weyland/keycloak-secret
  weyland/lakefs-creds
  weyland/lightdash-api-token
  weyland/litellm-secrets
  weyland/mlflow-auth
  weyland/mlflow-secret
  weyland/neo4j-secret
  weyland/open-webui-oauth
  weyland/port-creds
  weyland/pr-lifecycle-github     # B131 — read-only GitHub PAT for the open-PR staleness watchdog
  weyland/port-pr-reconcile-creds # B144 — Port org creds for the githubPullRequest reaper. DELIBERATELY NOT
                                  # weyland/port-creds: that one is mounted by dagster-user-code and, as of
                                  # 2026-08-25, holds the literal placeholders YOUR_ID / YOUR_SECRET (401).
  weyland/port-ingest-url
  weyland/ray-auth
  weyland/registry-auth
  weyland/sonarqube-scan-token
  weyland/sonarqube-secret
  weyland/tool-server-sentry
  weyland/traefik-forward-auth-secret
  weyland/unleash-secret
  weyland/weyland-postgres-secret
  # --- port-k8s-exporter (1) ---
  # B145 — the exporter's Port ORG credentials. Created imperatively with the hand-run `helm install`
  # and never sealed: it had NO ownerReferences at all, so nothing in git could restore it. The exporter
  # feeds the entire k8s half of the Port catalog, so losing this secret silently empties that catalog.
  port-k8s-exporter/weyland-cluster-port-k8s-exporter
  # --- data-mesh (15) ---
  data-mesh/clickhouse-users
  data-mesh/cube-secret
  data-mesh/dagster-postgres-secret
  data-mesh/datahub-ingestion-secrets
  data-mesh/datahub-oidc
  data-mesh/gizmosql-secret
  data-mesh/lakefs-creds
  data-mesh/lakefs-secret             # ⚠ bricking: AUTH_ENCRYPT_SECRET_KEY — also escrow off-cluster
  data-mesh/mongodb-secret
  data-mesh/musicbrainz-postgres-secret
  data-mesh/mysql-secret
  data-mesh/nessie-secret
  data-mesh/timescaledb-secret
  data-mesh/trino-metrics-auth
  data-mesh/trino-secret
  # --- monitoring (6) ---
  monitoring/grafana-admin
  monitoring/grafana-oauth
  monitoring/loki-minio
  monitoring/pve-exporter-secret
  monitoring/watchdog-healthcheck
  monitoring/weyland-alerts-telegram
  # --- minio (2) ---
  minio/minio-creds
  minio/minio-oidc
  # --- n8n (2) ---
  n8n/n8n-secret                      # ⚠ bricking: N8N_ENCRYPTION_KEY — also escrow off-cluster
  n8n/weyland-lab-ssh-key
  # --- jupyterhub (6) ---
  jupyterhub/jupyterhub-oidc
  jupyterhub/lakefs-creds
  jupyterhub/iceberg-s3-creds         # B81 storage nb 11 — Nessie/Iceberg warehouse S3 creds (access_key/secret_key)
  jupyterhub/gizmosql-creds           # B81 query nb 21 — GizmoSQL Flight SQL creds (GIZMOSQL_USERNAME/PASSWORD)
  jupyterhub/tier2-creds              # B81 query nb 22 — shared Tier-2 store password (ClickHouse/Mongo/Timescale/MySQL)
  jupyterhub/neo4j-creds              # B81 vector/graph nb 33 — Neo4j bolt password (NEO4J_PASSWORD)
  # --- gatekeeper-system (1) ---
  gatekeeper-system/gpm-secret
)

command -v kubeseal >/dev/null || { echo "kubeseal not found"; exit 1; }
[ "$SEAL" = 1 ] && { mkdir -p "$OUT"; echo "sealing ${#SECRETS[@]} secrets -> $OUT"; } \
                || echo "DRY RUN — ${#SECRETS[@]} secrets in allow-list. Add --seal to write CRs."

miss=0
for entry in "${SECRETS[@]}"; do
  ns="${entry%%/*}"; name="${entry#*/}"
  if ! kubectl -n "$ns" get secret "$name" >/dev/null 2>&1; then
    echo "  MISSING     $ns/$name  (not in cluster — check the name)"; miss=$((miss+1)); continue
  fi
  if [ "$SEAL" = 1 ]; then
    kubectl -n "$ns" annotate secret "$name" sealedsecrets.bitnami.com/managed=true --overwrite >/dev/null
    kubectl -n "$ns" get secret "$name" -o yaml | kubeseal --format yaml > "$OUT/${ns}__${name}.yaml"
    echo "  sealed      $ns/$name"
  else
    echo "  ok          $ns/$name"
  fi
done
echo "---"
[ "$miss" -gt 0 ] && echo "⚠ $miss MISSING — fix the name(s) before --seal."
[ "$SEAL" = 1 ] && echo "Done. rsync '$OUT/' -> repo k8s/sealed-secrets/sealed/ , then commit + push (Argo applies)." \
                || echo "Allow-list validated above. Re-run with --seal when it looks right."
