#!/usr/bin/env bash
# B101 — push an image to the MinIO-backed registry and VERIFY the manifest finalized, re-pushing if it didn't.
#
# The registry (registry.weyland.lab — distribution/registry, S3 driver → MinIO on the uas-quirked USB disk)
# intermittently completes the blob layers but drops the manifest PUT → the tag is absent → pods ImagePullBackOff
# with "not found" even though the blobs are present. A re-push (blobs already there = fast) re-sends the small
# manifest, which lands. This wraps push + verify + retry so a deploy is one command instead of a manual round-trip.
#
# Usage:  scripts/push-image.sh registry.weyland.lab/<name>:<tag>
# Env:    PUSH_ATTEMPTS (default 3)
set -euo pipefail

ref="${1:?usage: push-image.sh registry.weyland.lab/<name>:<tag>}"
registry="${ref%%/*}"          # registry.weyland.lab
path="${ref#*/}"               # <name>:<tag>
name="${path%:*}"              # <name>
tag="${path##*:}"              # <tag>
attempts="${PUSH_ATTEMPTS:-3}"

for i in $(seq 1 "$attempts"); do
    docker push "$ref"
    # The manifest is finalized only when the tag appears in the registry's tags/list.
    if curl -sf "https://${registry}/v2/${name}/tags/list" | grep -q "\"${tag}\""; then
        echo "✅ ${name}:${tag} manifest finalized (attempt ${i}/${attempts})"
        exit 0
    fi
    echo "⚠️  ${name}:${tag} manifest NOT finalized — re-pushing (attempt ${i}/${attempts})..."
    sleep 2
done

echo "❌ ${name}:${tag} still missing from the registry after ${attempts} attempts — inspect the registry pod/logs." >&2
exit 1
