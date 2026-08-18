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

  buildctl-daemonless.sh build \
    --frontend dockerfile.v0 \
    --local "context=${ctxpath}" \
    --local "dockerfile=${ctxpath}" \
    --opt "filename=${dfname}" \
    --output "type=image,name=${REG}/${image}:${newtag},push=true,registry.insecure=true" \
    --export-cache "type=registry,ref=${REG}/${image}:buildcache,mode=max,registry.insecure=true" \
    --import-cache "type=registry,ref=${REG}/${image}:buildcache,registry.insecure=true"

  printf '%s\t%s\t%s\n' "$image" "$newtag" "$manifests" >> "$BUMPS"
  echo "[build] pushed ${REG}/${image}:${newtag}"
done < "$PLAN"

echo "[build] done — $(wc -l < "$BUMPS" | tr -d ' ') image(s) pushed."
