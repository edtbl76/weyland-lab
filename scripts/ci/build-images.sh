#!/bin/sh
# B57a step 2 — build + push the images named in the plan, using rootless BuildKit (daemonless — no always-on
# daemon; best for the RAM-tight single node). Warm-cache via a registry-backed cache tag so unchanged layers
# aren't rebuilt. Runs in moby/buildkit:rootless, from the repo root. Registry is LAN mkcert-TLS + no-auth →
# registry.insecure=true (matches the nodes' registries.yaml insecure_skip_verify).
# Input:  $PLAN  = "image<TAB>context<TAB>newtag<TAB>manifests"   (from detect-changes.sh)
# Output: $BUMPS = "image<TAB>newtag<TAB>manifests"               (only images that built+pushed OK)
set -eu

PLATFORM="nodes/mother/lab/weyland-platform"
PLAN="${PLAN:-.ci-build-plan}"
BUMPS="${BUMPS:-.ci-image-bumps}"
REG="registry.weyland.lab"
: > "$BUMPS"

[ -s "$PLAN" ] || { echo "[build] empty plan — nothing to build."; exit 0; }

# Thin client: build against the persistent buildkitd Deployment (k8s/woodpecker/buildkitd.yaml), NOT a daemon in
# this step pod — daemonless BuildKit can't do its snapshot mounts inside an ephemeral Woodpecker step pod on this
# cluster (EPERM). buildkitd does the mounts in its own stable mnt ns. This step mounts nothing.
BK_ADDR="${BUILDKIT_HOST:-tcp://buildkitd:1234}"
echo "[build] using buildkitd at ${BK_ADDR}"
buildctl --addr "$BK_ADDR" debug workers >/dev/null 2>&1 || { echo "[build] buildkitd not reachable at ${BK_ADDR}"; exit 1; }

while IFS="$(printf '\t')" read -r image context newtag manifests; do
  [ -n "$image" ] || continue
  # split "<dir>" or "<dir>::<dockerfile-relpath>"
  ctxdir="${context%%::*}"
  case "$context" in
    *::*) dfname="${context##*::}" ;;
    *)    dfname="Dockerfile" ;;
  esac
  ctxpath="${PLATFORM}/${ctxdir}"
  echo "==== [build] ${image}:${newtag}  (context ${ctxdir}, dockerfile ${dfname}) ===="

  buildctl --addr "$BK_ADDR" build \
    --frontend dockerfile.v0 \
    --local "context=${ctxpath}" \
    --local "dockerfile=${ctxpath}" \
    --opt "filename=${dfname}" \
    --output "type=image,name=${REG}/${image}:${newtag},push=true,registry.insecure=true" \
    --export-cache "type=registry,ref=${REG}/${image}:buildcache,mode=max,registry.insecure=true" \
    --import-cache "type=registry,ref=${REG}/${image}:buildcache,registry.insecure=true"

  printf '%s\t%s\t%s\n' "$image" "$newtag" "$manifests" >> "$BUMPS"
  echo "[build] pushed ${REG}/${image}:${newtag}"

  # ── B88 Phase 3 — supply chain, per pushed image ──────────────────────────────────────────────
  # SBOM + signature + SLSA provenance + licence scan. This runs AFTER a successful push (there is
  # nothing to sign before one) and MUST NOT abort the build: an image that shipped but was not
  # signed is a gap to fix, whereas failing the pipeline here would make a signing-tool hiccup look
  # like a broken build. Same contract as the DORA emit in ship-images.sh — loud, non-fatal.
  #
  # It is NOT silent either. A swallowed failure means unsigned images accumulate while the
  # pipeline stays green, which is exactly the absence-as-success shape B88 exists to remove.
  if [ -x "${REPO_ROOT:-.}/scripts/supply-chain.sh" ] || [ -f "scripts/supply-chain.sh" ]; then
    if ! bash scripts/supply-chain.sh all "${REG}/${image}:${newtag}"; then
      echo "  !! supply-chain step FAILED for ${REG}/${image}:${newtag} — image shipped UNSIGNED /"
      echo "  !! without an SBOM. The build is not failed for this, but the gap is real: re-run"
      echo "  !! scripts/supply-chain.sh all <image> once the cause is fixed."
    fi
  fi
done < "$PLAN"

echo "[build] done — $(wc -l < "$BUMPS" | tr -d ' ') image(s) pushed."
