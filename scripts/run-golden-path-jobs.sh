#!/usr/bin/env bash
# Ephemeral golden-path exerciser (B153) — spin each golden path up in-cluster, then tear it down.
#
# For each golden path (a golden-paths/<lang>/<framework>/ dir with a Dockerfile), this:
#   1. builds the image via buildkit → registry.weyland.lab/golden-<lang>-<framework>   (on mother)
#   2. applies a run-to-completion k8s Job that runs the image's ephemeral smoke (proves it SERVES)
#   3. waits for the Job, asserts it completed (exit 0), prints its log
#   4. DELETES the Job — nothing is left running (golden paths are never Deployments)
#
# This is the "runnable + ephemeral" half of the contract: it proves the built image runs on the real
# platform without occupying it. The "extendable" half is scripts/new-service.sh (scaffold FROM a path).
#
#   usage: run-golden-path-jobs.sh [<lang>/<framework> ...]   (default: all golden paths with a Dockerfile)
#          --dry-run   print the images + Jobs it would build/apply, change nothing
#
# EXIT: 0 all exercised paths' smoke passed · 1 a smoke failed (named) · 2 could not run (build/apply).
# OPERATOR STEP: the buildkit build + Job apply touch the cluster; run from mother/rogueone with kube +
# buildkit access. Fail-closed: a build or apply failure is exit 2, never a silent pass.
set -uo pipefail
. "$(dirname "$0")/lib/common.sh"
GP_DIR="$REPO_ROOT/golden-paths"
NS="${GOLDEN_PATH_NS:-weyland}"
REGISTRY="${GOLDEN_PATH_REGISTRY:-registry.weyland.lab}"
# buildkitd is the Woodpecker CI builder and lives in the `woodpecker` namespace (the estate's only
# buildkitd) — NOT `weyland`. This exerciser builds via buildctl against it, so it runs IN-CLUSTER
# (a CI step or a pod with buildctl) or through a port-forward to buildkitd.woodpecker.svc:1234; it is
# not runnable from a host that can't resolve the cluster-internal service.
BUILDKIT="${BUILDKIT_ADDR:-tcp://buildkitd.woodpecker.svc:1234}"
DRY=0; TARGETS=()
for a in "$@"; do case "$a" in --dry-run) DRY=1 ;; *) TARGETS+=("$a") ;; esac; done

# Resolve the golden paths to exercise: explicit args, else every dir with a Dockerfile.
paths=()
if [ "${#TARGETS[@]}" -gt 0 ]; then
  for t in "${TARGETS[@]}"; do [ -f "$GP_DIR/$t/Dockerfile" ] && paths+=("$t") || { echo "no golden path with a Dockerfile at $t" >&2; exit 2; }; done
else
  while IFS= read -r df; do paths+=("$(dirname "${df#"$GP_DIR"/}")"); done < <(find "$GP_DIR" -name Dockerfile 2>/dev/null | sort)
fi
[ "${#paths[@]}" -gt 0 ] || { echo "no golden paths found under $GP_DIR" >&2; exit 2; }

fail=0
for p in "${paths[@]}"; do
  name="golden-$(printf '%s' "$p" | tr '/' '-')"      # golden-paths/python/fastapi -> golden-python-fastapi
  image="$REGISTRY/$name:latest"
  job="gp-$(printf '%s' "$p" | tr '/' '-')"
  # Each golden path declares its ephemeral smoke command in a `.smoke` file (e.g. `python smoke.py`,
  # `sh smoke.sh`), run via `sh -c` so it is language-agnostic. Fail closed if it is missing.
  smoke="$(cat "$GP_DIR/$p/.smoke" 2>/dev/null || true)"
  [ -n "$smoke" ] || { echo "no .smoke command for $p (add golden-paths/$p/.smoke)" >&2; exit 2; }

  if [ "$DRY" -eq 1 ]; then
    echo "would build $image from golden-paths/$p (buildkit $BUILDKIT) and run Job $job/$NS (smoke: $smoke)"
    continue
  fi

  echo "== $p =="
  buildctl --addr "$BUILDKIT" build \
    --frontend dockerfile.v0 --local context="$GP_DIR/$p" --local dockerfile="$GP_DIR/$p" \
    --output "type=image,name=$image,push=true" || { echo "BUILD FAILED: $image" >&2; exit 2; }

  kubectl -n "$NS" delete job "$job" --ignore-not-found >/dev/null 2>&1
  kubectl -n "$NS" apply -f - >/dev/null <<EOF || { echo "APPLY FAILED: $job" >&2; exit 2; }
apiVersion: batch/v1
kind: Job
metadata: { name: $job, namespace: $NS, labels: { app: golden-path, "golden-path/name": "$name" } }
spec:
  backoffLimit: 0
  activeDeadlineSeconds: 180
  ttlSecondsAfterFinished: 300
  template:
    metadata: { labels: { "sidecar.istio.io/inject": "false" } }
    spec:
      restartPolicy: Never
      containers:
        - name: smoke
          image: $image
          command: ["sh", "-c", "$smoke"]
          resources: { requests: { cpu: 25m, memory: 64Mi }, limits: { memory: 256Mi } }
EOF

  if kubectl -n "$NS" wait --for=condition=complete "job/$job" --timeout=180s >/dev/null 2>&1; then
    echo "  SMOKE OK"; kubectl -n "$NS" logs "job/$job" 2>/dev/null | tail -1
  else
    echo "  SMOKE FAILED for $p:" >&2; kubectl -n "$NS" logs "job/$job" 2>/dev/null | tail -5 >&2; fail=1
  fi
  kubectl -n "$NS" delete job "$job" --ignore-not-found >/dev/null 2>&1   # tear down — ephemeral
done

[ "$DRY" -eq 1 ] && { echo "dry-run — ${#paths[@]} golden path(s) planned, nothing built or applied."; exit 0; }
[ "$fail" -eq 0 ] && { echo "OK — all ${#paths[@]} golden path(s) served in-cluster and were torn down."; exit 0; }
echo "a golden path smoke failed (see above)" >&2; exit 1
