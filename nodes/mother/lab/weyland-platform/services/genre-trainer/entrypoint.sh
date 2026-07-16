#!/usr/bin/env bash
# Self-contained cluster access. The image is handed only a kubeconfig (mounted). From that, kubectl does
# everything the trainer needs against the cluster:
#   (1) reads the creds from the k8s Secrets -> exports them (no secrets on the command line);
#   (2) opens port-forwards to mlflow/minio/lakefs on the CONTAINER's own localhost -- no host port-forwards, no
#       --network host, no host-loopback issues (rogueone runs Docker Desktop, whose --network host is the VM's).
# The container reaches the k8s API (mother:6443 on the LAN) directly; then it execs the pure-Python trainer.
set -euo pipefail

get_secret() { kubectl -n "$1" get secret "$2" -o "jsonpath={.data.$3}" | base64 -d; }

echo "[entrypoint] reading creds from k8s Secrets via the mounted kubeconfig..."
export LAKEFS_ACCESS_KEY_ID=${LAKEFS_ACCESS_KEY_ID:-$(get_secret weyland lakefs-creds LAKEFS_ACCESS_KEY_ID)}
export LAKEFS_SECRET_ACCESS_KEY=${LAKEFS_SECRET_ACCESS_KEY:-$(get_secret weyland lakefs-creds LAKEFS_SECRET_ACCESS_KEY)}
export AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID:-$(get_secret weyland aidlc-kb-minio-secret access_key)}
export AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY:-$(get_secret weyland aidlc-kb-minio-secret secret_key)}
# B47: Ray token auth — the trainer connects to the head's authed cluster (ray.init address=auto), so it needs the
# shared token. Read it from the same ray-auth Secret the head + rogueone worker use.
export RAY_AUTH_MODE=token
export RAY_AUTH_TOKEN=${RAY_AUTH_TOKEN:-$(get_secret weyland ray-auth token)}

start_pf() {  # namespace svc localport remoteport
  kubectl port-forward -n "$1" "svc/$2" "$3:$4" >/dev/null 2>&1 &
  echo "[entrypoint] port-forward $1/$2 -> localhost:$3"
}

echo "[entrypoint] opening in-container port-forwards..."
start_pf weyland   mlflow 5000 5000
start_pf minio     minio  9000 9000
start_pf data-mesh lakefs 8000 8000

wait_port() {  # host port -- poll until the forward accepts a TCP connection (or give up)
  for _ in $(seq 1 30); do
    (exec 3<>"/dev/tcp/$1/$2") 2>/dev/null && { exec 3<&-; echo "[entrypoint] $1:$2 ready"; return 0; }
    sleep 1
  done
  echo "[entrypoint] TIMEOUT waiting for $1:$2 -- is the service/kubeconfig reachable?" >&2
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
