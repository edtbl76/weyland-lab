#!/usr/bin/env bash
# ESCAPE HATCH ONLY — the CI pipeline (B57a) owns these images in normal operation.
#
# This builds the SAME 11 images that scripts/ci/images.tsv tracks — verified identical 2026-08-21, the two
# lists match exactly. So on any ordinary change you do NOT run this: push, trigger the pipeline, merge the
# tag-bump PR. This exists for when that lane is unavailable — buildkitd down, Woodpecker wedged, cluster
# unreachable — because it builds with plain `docker` on the dev machine and depends on none of that.
#
# HEADER CORRECTED 2026-08-21. It previously said "all 8 images" (it builds 11) and described the retired
# `:vN` hand-bump convention as if it were current. It also does NOT build `ranger` — the codekb claimed it
# did; there is no `build ranger` line here. Nothing in this repo builds ranger, or the nine other `:vN`
# images (weyland-operator, weyland-guard, realm-of-agents, ray-head, …); those are built by hand and
# undocumented. B135 phase 2 brings them into CI.
#
# TAG DEFAULTS TO THE CI CONVENTION (`git-<short-sha>`) so an emergency build lands on the tag the manifests
# already reference and the node re-pulls it. The old `:v1` default was a trap: it pushed tags no manifest
# pointed at, so the build appeared to succeed and changed nothing. Override deliberately if you need to:
#
#   ./build-push-images.sh              # build + push all 11 at git-<sha> of the current HEAD
#   TAG=v9 ./build-push-images.sh       # explicit tag — you must then bump the manifest refs yourself
#
# ORDER when using an explicit TAG: run this FIRST (images land in the registry), THEN push the repointed
# manifests — else Argo redeploys into ImagePullBackOff.
#
# Run on the DEV MACHINE (has docker + can push to the registry; k3s nodes pull via node-level containerd
# auth, so no imagePullSecret is needed).
set -euo pipefail
REG="${REG:-registry.weyland.lab}"
# Match scripts/ci/build-images.sh: git-<short-sha>. Falls back to v1 only outside a git checkout.
TAG="${TAG:-git-$(git rev-parse --short=8 HEAD 2>/dev/null || echo v1)}"
. "$(dirname "$0")/lib/common.sh"
cd "$PLATFORM_DIR"   # build contexts below are relative to the platform dir

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
