#!/usr/bin/env bash
# Self-contained cluster access. The image is handed only a kubeconfig (mounted). From that, kubectl does
# everything the trainer needs against the cluster:
#   (1) reads the creds from the k8s Secrets -> exports them (no secrets on the command line);
#   (2) points the trainer at the LAN NodePorts of mlflow/minio/lakefs (mlflow-lan :30500, minio-s3-lan :30990,
#       lakefs-lan :30800) and checks each answers before training. NodePorts only (AGENTS.md); bridge networking
#       reaches the LAN directly, so there is no --network host / host-loopback issue either.
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

LAN=${WEYLAND_LAN_HOST:-192.168.1.243}   # mother: the NodePorts below are on its LAN address

wait_port() {  # host port -- poll until the NodePort accepts a TCP connection (or give up)
  for _ in $(seq 1 30); do
    (exec 3<>"/dev/tcp/$1/$2") 2>/dev/null && { exec 3<&-; echo "[entrypoint] $1:$2 ready"; return 0; }
    sleep 1
  done
  echo "[entrypoint] TIMEOUT waiting for $1:$2 -- is the service/kubeconfig reachable?" >&2
  return 1
}
wait_port "$LAN" 30500   # mlflow-lan (admits rogueone only)
wait_port "$LAN" 30990   # minio-s3-lan
wait_port "$LAN" 30800   # lakefs-lan

# Point the trainer at the NodePorts (overridable).
export MLFLOW_TRACKING_URI=${MLFLOW_TRACKING_URI:-http://$LAN:30500}
export MLFLOW_S3_ENDPOINT_URL=${MLFLOW_S3_ENDPOINT_URL:-http://$LAN:30990}
export LAKEFS_ENDPOINT=${LAKEFS_ENDPOINT:-http://$LAN:30800}
export LAKEFS_BRANCH=${LAKEFS_BRANCH:-main}
export AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-us-east-1}

exec python train_volatility.py "$@"
