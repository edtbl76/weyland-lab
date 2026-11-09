#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="$(dirname "$SCRIPT_DIR")"
K8S_DIR="$(dirname "$(dirname "$SERVICE_DIR")")/k8s"
ENV_FILE="${SERVICE_DIR}/.env"
NAMESPACE="weyland"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: ${ENV_FILE} not found. Copy .env.example and fill in values." >&2
  exit 1
fi

set -a
source "$ENV_FILE"
set +a

: "${APISIX_ADMIN_KEY:?APISIX_ADMIN_KEY must be set in .env}"
: "${APISIX_DASHBOARD_SECRET:?APISIX_DASHBOARD_SECRET must be set in .env}"
: "${APISIX_DASHBOARD_PASSWORD:?APISIX_DASHBOARD_PASSWORD must be set in .env}"

echo "==> Applying APISIX k8s manifests..."
kubectl apply -f "${K8S_DIR}/apisix-etcd.yaml"

echo "==> Creating apisix-config ConfigMap..."
envsubst < "${SERVICE_DIR}/conf/config.yaml" \
  | kubectl create configmap apisix-config \
      --from-file=config.yaml=/dev/stdin \
      --namespace="$NAMESPACE" \
      --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f "${K8S_DIR}/apisix.yaml"

echo "==> Creating apisix-secret..."
kubectl create secret generic apisix-secret \
  --from-literal=APISIX_ADMIN_KEY="$APISIX_ADMIN_KEY" \
  --namespace="$NAMESPACE" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "==> Creating apisix-dashboard-config ConfigMap..."
envsubst < "${SERVICE_DIR}/dashboard/conf.yaml.template" \
  | kubectl create configmap apisix-dashboard-config \
      --from-file=conf.yaml=/dev/stdin \
      --namespace="$NAMESPACE" \
      --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f "${K8S_DIR}/apisix-dashboard.yaml"

echo "==> Waiting for APISIX to be ready..."
kubectl rollout status deployment/weyland-apisix -n "$NAMESPACE" --timeout=120s

echo "==> Restoring routes into etcd..."
# B239 (2026-11-08): the routes are defined in scripts/lib/apisix_routes.py and written to etcd with etcdctl. The old
# step (copy conf/routes-init.sh into the gateway pod and run it) could not work: the gateway image has no curl.
python3 "$(git -C "$SERVICE_DIR" rev-parse --show-toplevel)/scripts/apisix-routes.py" restore

echo ""
echo "APISIX deployed."
echo "  Gateway:   http://mother:30090"
echo "  Dashboard: http://mother:30091  (admin / see .env)"
