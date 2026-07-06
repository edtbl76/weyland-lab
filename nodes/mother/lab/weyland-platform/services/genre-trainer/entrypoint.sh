#!/usr/bin/env bash
# Self-contained networking. The image is handed only a kubeconfig (mounted) — it then opens its OWN
# port-forwards to the cluster services it needs, onto the CONTAINER's localhost, and trains against those.
# No host port-forwards, no --network host, no host-loopback gymnastics: the container reaches the k8s API
# (mother:6443 on the LAN) and forwards mlflow/minio/lakefs to itself. kubectl uses the mounted ~/.kube/config.
set -euo pipefail

start_pf() {  # namespace svc localport remoteport
  kubectl port-forward -n "$1" "svc/$2" "$3:$4" >/dev/null 2>&1 &
  echo "[entrypoint] port-forward $1/$2 → localhost:$3"
}

echo "[entrypoint] opening in-container port-forwards via the mounted kubeconfig…"
start_pf weyland   mlflow 5000 5000
start_pf minio     minio  9000 9000
start_pf data-mesh lakefs 8000 8000

wait_port() {  # host port — poll until the forward accepts a TCP connection (or give up)
  for _ in $(seq 1 30); do
    (exec 3<>"/dev/tcp/$1/$2") 2>/dev/null && { exec 3<&-; echo "[entrypoint] $1:$2 ready"; return 0; }
    sleep 1
  done
  echo "[entrypoint] TIMEOUT waiting for $1:$2 — is the service/kubeconfig reachable?" >&2
  return 1
}
wait_port localhost 5000
wait_port localhost 9000
wait_port localhost 8000

# Point the trainer at its own forwards (overridable, but these are the defaults now).
export MLFLOW_TRACKING_URI=${MLFLOW_TRACKING_URI:-http://localhost:5000}
export MLFLOW_S3_ENDPOINT_URL=${MLFLOW_S3_ENDPOINT_URL:-http://localhost:9000}
export LAKEFS_ENDPOINT=${LAKEFS_ENDPOINT:-http://localhost:8000}
export LAKEFS_BRANCH=${LAKEFS_BRANCH:-main}
export AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-us-east-1}

exec python train_genre.py "$@"
