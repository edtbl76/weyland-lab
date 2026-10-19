#!/usr/bin/env bash
# ESCAPE HATCH ONLY — the CI pipeline (B57a) owns these images in normal operation.
#
# This builds the SAME 11 images that scripts/ci/images.tsv tracks — verified identical 2026-08-21, the two
# lists match exactly. So on any ordinary change you do NOT run this: push, trigger the pipeline, merge the
# tag-bump PR. This exists for when that lane is unavailable — buildkitd down, Woodpecker wedged, cluster
# unreachable — because it builds with plain `docker` on the dev machine and depends on none of that.
#
# HEADER CORRECTED 2026-08-21. It previously said "all 8 images" (it builds 11) and described the retired
# `:vN` hand-bump convention as if it were current. It builds `ranger` only when RANGER_TAG names the next free tag
# (see the ranger block at the end). The other hand-tagged `:vN` images (ray-head, …) are built by hand. (realm-of-agents moved into CI 2026-10-08, B202;
# weyland-guard 2026-10-14, B207 — see docs/runbooks/guardrails.md § Build & deploy for its escape-hatch build.)
# B135 phase 2 brings them into CI (weyland-operator moved into scripts/ci/images.tsv 2026-10-02).
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
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"   # absolute: the build() pushes run after the cd below
# Match scripts/ci/build-images.sh: git-<short-sha>. Falls back to v1 only outside a git checkout.
TAG="${TAG:-git-$(git rev-parse --short=8 HEAD 2>/dev/null || echo v1)}"
. "$(dirname "$0")/lib/common.sh"
cd "$PLATFORM_DIR"   # build contexts below are relative to the platform dir

# B211: push through push-image.sh, which pushes to the authenticated push host and verifies via the pull name.
build() { echo "==== $1:$TAG ===="; docker build -t "$REG/$1:$TAG" $2; bash "$SCRIPT_DIR/push-image.sh" "$REG/$1:$TAG"; }

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

# ranger is VERSION-PINNED (mr3project base tag), not TAG-following — built only when RANGER_TAG names the NEXT FREE
# tag (B92: was a local ctr-import, moved to the registry). Never a fixed tag here: this line used to rebuild
# `2.6.0-py3` — the ROLLBACK image since B220 moved the deployment to `2.6.0-py3-r2` — and a push silently overwrites
# an existing tag (2026-10-19 DoD audit). List first: curl -s https://registry.weyland.lab/v2/ranger/tags/list
if [ -n "${RANGER_TAG:-}" ]; then
  echo "==== ranger:$RANGER_TAG (version-pinned) ===="; docker build -t "$REG/ranger:$RANGER_TAG" services/ranger; bash "$SCRIPT_DIR/push-image.sh" "$REG/ranger:$RANGER_TAG"
else
  echo "---- ranger skipped: set RANGER_TAG to the next free tag to build it (docs/runbooks/ranger.md) ----"
fi

echo "---- done: images at :$TAG${RANGER_TAG:+ + ranger:$RANGER_TAG} pushed to $REG. Now push the repointed k8s manifests so Argo redeploys. ----"
