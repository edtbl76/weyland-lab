#!/usr/bin/env bash
# B69 Wave 3 — build + push the weyland-built images to registry.weyland.lab, off the :local / imagePullPolicy:Never
# path so pods survive a reschedule or node rebuild (no more ErrImageNeverPull). Run on ROGUEONE (has docker + can
# push to the registry; k3s nodes pull via node-level containerd auth — no imagePullSecret needed).
#
#   ./build-push-images.sh          # build + push all 8 images at TAG (default v1)
#   TAG=v2 ./build-push-images.sh   # rebuild at a NEW tag on change, then bump the manifest image refs to :v2 + push
#
# IfNotPresent + a stable tag means a NEW tag is what makes nodes re-pull (same convention as ray-head:vN). So on a
# real change: bump TAG here AND in the manifest(s). ORDER: run this FIRST (images land in the registry), THEN push
# the repointed manifests — else Argo redeploys into ImagePullBackOff.
set -euo pipefail
REG="${REG:-registry.weyland.lab}"
TAG="${TAG:-v1}"
cd "$(dirname "$0")/.."   # -> nodes/mother/lab/weyland-platform ; build contexts below are relative to here

build() { echo "==== $1:$TAG ===="; docker build -t "$REG/$1:$TAG" $2; docker push "$REG/$1:$TAG"; }

build weyland-tool-server       "services/weyland-tool-server"
build weyland-rag-index         "services/rag-index"
build weyland-dagster-base      "services/weyland-dagster-base"
build weyland-dagster-user-code "services/weyland-dagster"
build feast-server              "-f services/weyland-dagster/Dockerfile.feast services/weyland-dagster"
build weyland-flink             "-f k8s/flink/Dockerfile k8s/flink"
build weyland-flink-py          "-f k8s/flink/Dockerfile.pyflink k8s/flink"
build store-scaler              "services/store-scaler"
build scan-suite                "services/scan-suite"
build guardrails-structure      "services/guardrails-structure"   # B115 Structure layer (guardrails-ai isolated)
build nemo-guardrails           "services/nemo-guardrails"        # B115 Dialog layer (NeMo Guardrails isolated)

# ranger is VERSION-PINNED (mr3project base tag), not TAG-following — build it explicitly (B92: was a local
# ctr-import, moved to the registry so it survives a prune/reschedule like the rest).
echo "==== ranger:2.6.0-py3 (version-pinned) ===="; docker build -t "$REG/ranger:2.6.0-py3" services/ranger; docker push "$REG/ranger:2.6.0-py3"

echo "---- done: 8 images at :$TAG + ranger:2.6.0-py3 pushed to $REG. Now push the repointed k8s manifests so Argo redeploys. ----"
