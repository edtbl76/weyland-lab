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

echo "==> Seeding routes via kubectl exec..."
APISIX_POD=$(kubectl get pod -n "$NAMESPACE" -l app=weyland-apisix -o jsonpath='{.items[0].metadata.name}')
kubectl cp "${SERVICE_DIR}/conf/routes-init.sh" \
  "${NAMESPACE}/${APISIX_POD}:/tmp/routes-init.sh"
kubectl exec -n "$NAMESPACE" "$APISIX_POD" -- \
  env APISIX_ADMIN_KEY="$APISIX_ADMIN_KEY" bash /tmp/routes-init.sh

echo ""
echo "APISIX deployed."
echo "  Gateway:   http://mother:30090"
echo "  Dashboard: http://mother:30091  (admin / see .env)"
