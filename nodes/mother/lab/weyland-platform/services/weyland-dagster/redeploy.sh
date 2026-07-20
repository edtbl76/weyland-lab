#!/usr/bin/env bash
# ⚠️ OBSOLETE AS A DEPLOY PATH — kept as a GUARD so it can't silently do nothing.
#
# This script used to build `weyland-dagster-user-code:local` and `ctr import` it into k3s containerd. **B69 Wave 3
# moved this image to `registry.weyland.lab/weyland-dagster-user-code:<TAG>` with `imagePullPolicy: IfNotPresent`**,
# so the old flow builds an image that NOTHING CONSUMES — while `rollout restart` still reports success and the pod
# comes back on the unchanged registry image.
#
# That false success cost real time on 2026-07-20: four full rebuilds, every step green, `successfully rolled out`
# each time, and the code never changed. The tell was `Step 7/15 COPY weyland_pipeline/ ---> Using cache` plus a
# schedule list that never grew. So this script now REFUSES to run when the deployment is on a registry image.
#
# THE CORRECT FLOW (registry + immutable tag; `IfNotPresent` means only a NEW TAG makes nodes re-pull):
#   1. [rogueone] TAG=v2 scripts/build-push-images.sh      # or build+push just this one image at the new tag
#   2. bump BOTH manifest refs to :v2 — k8s/dagster/user-code.yaml AND k8s/dagster/dbt-docs.yaml
#   3. push -> Argo redeploys
#   ORDER MATTERS: images to the registry FIRST, manifests second, or Argo lands in ImagePullBackOff.
set -euo pipefail

LIVE_IMAGE="$(kubectl -n weyland get deploy dagster-user-code \
  -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || echo "")"

if [[ "$LIVE_IMAGE" != *":local" ]]; then
  cat >&2 <<EOF
!! REFUSING TO RUN — this script is obsolete for the current deployment.

   dagster-user-code runs: ${LIVE_IMAGE:-<could not read deployment>}
   This script builds:     weyland-dagster-user-code:local   (nothing consumes it)

   Building + ctr-importing :local would appear to succeed and change NOTHING.

   Do this instead (see docs/runbooks/dagster.md + scripts/build-push-images.sh):
     1. [rogueone] TAG=vN scripts/build-push-images.sh
     2. bump the image tag in k8s/dagster/user-code.yaml AND k8s/dagster/dbt-docs.yaml
     3. push -> Argo redeploys (images to the registry FIRST, manifests second)
EOF
  exit 1
fi

# --- legacy path, only reachable if the deployment is genuinely back on a :local image ---
IMAGE="weyland-dagster-user-code:local"
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> [1/4] docker build ${IMAGE}  (context: ${DIR})"
docker build -t "${IMAGE}" "${DIR}"

echo "==> [2/4] import into k3s containerd (k8s.io namespace)"
docker save "${IMAGE}" | sudo ctr -n k8s.io images import -

echo "==> [3/4] rollout restart dagster-user-code"
kubectl -n weyland rollout restart deploy/dagster-user-code
kubectl -n weyland rollout status deploy/dagster-user-code --timeout=180s

echo "==> [4/4] verify the store-loader deps import inside the new pod"
kubectl -n weyland exec deploy/dagster-user-code -- \
  python -c "import clickhouse_connect, cassandra, pymongo, sqlalchemy_cockroachdb, opensearchpy, neo4j, qdrant_client, weaviate, sentence_transformers, librosa, confluent_kafka, lancedb; print('store-loader imports OK')" \
  || echo "!! import check failed — inspect the pod (does not fail the deploy)"

echo "==> done."
