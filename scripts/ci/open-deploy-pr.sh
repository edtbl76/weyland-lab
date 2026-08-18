#!/bin/sh
# B57a step 4 — deploy handoff (git-as-seam; CI never calls `argocd sync`). For every image that built, bump its
# tag in the tracked manifests, push a branch, and open ONE PR against main. YOU merge it → Argo reconciles → rollout.
# Runs in a git+curl image from the repo root. Needs $GITHUB_TOKEN (fine-grained PAT: Contents:write + Pull requests:write on edtbl76/weyland-lab).
# Input: $BUMPS = "image<TAB>newtag<TAB>manifests"  (from build-images.sh)
set -eu

PLATFORM="nodes/mother/lab/weyland-platform"
BUMPS="${BUMPS:-.ci-image-bumps}"
REG="registry.weyland.lab"
REPO="edtbl76/weyland-lab"
BASE="main"

[ -s "$BUMPS" ] || { echo "[handoff] no images built — nothing to deploy."; exit 0; }
: "${GITHUB_TOKEN:?GITHUB_TOKEN not set — add the fine-grained PAT as the Woodpecker repo secret 'github_token'}"

NEWTAG="$(awk 'NR==1{print $2}' "$BUMPS")"          # all bumps in a run share the HEAD tag
SHA="${NEWTAG#git-}"
BRANCH="ci/image-bump-${SHA}"
IMAGES=""

# rewrite each tracked manifest's image tag to the new one
while IFS="$(printf '\t')" read -r image newtag manifests; do
  [ -n "$image" ] || continue
  IMAGES="${IMAGES} ${image}"
  for m in $manifests; do
    f="${PLATFORM}/${m}"
    [ -f "$f" ] || { echo "[handoff] WARN missing manifest ${f} — skipping"; continue; }
    sed -i -E "s#(${REG}/${image}):[A-Za-z0-9._-]+#\1:${newtag}#g" "$f"
    echo "[handoff] ${m} → ${image}:${newtag}"
  done
done < "$BUMPS"

git config user.email "ci@weyland.lab"
git config user.name  "weyland-ci"
git checkout -b "$BRANCH"
git commit -am "ci: bump${IMAGES} to ${NEWTAG}"

# push the branch (token in the URL, never logged)
git push -q "https://x-access-token:${GITHUB_TOKEN}@github.com/${REPO}.git" "HEAD:${BRANCH}" 2>/dev/null
echo "[handoff] pushed branch ${BRANCH}"

# open the PR. Body uses literal \n (valid JSON); image names/tags are [A-Za-z0-9._/-] only → no escaping needed.
# 422 = a PR for this head is already open → not an error.
list=""
while IFS="$(printf '\t')" read -r image newtag manifests; do
  [ -n "$image" ] && list="${list}- ${image} → ${newtag}\\n"
done < "$BUMPS"
body="Automated image bump from Woodpecker CI (B57a).\\n\\nImages → ${NEWTAG}:\\n${list}\\nMerge to deploy — Argo CD reconciles main → rollout. Do NOT drop the tag from the manifests."

payload="$(printf '{"title":"ci: image bump%s → %s","head":"%s","base":"%s","body":"%s"}' \
  "$IMAGES" "$NEWTAG" "$BRANCH" "$BASE" "$body")"

resp="$(curl -sf -X POST \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/${REPO}/pulls" \
  -d "$payload" 2>/dev/null)" || {
    echo "[handoff] PR create returned non-2xx (a PR for ${BRANCH} may already be open) — verify on GitHub."; exit 0; }

echo "[handoff] PR opened: $(printf '%s' "$resp" | grep -oE '"html_url"[^,]*' | head -n1 | sed 's/.*: *//; s/"//g')"
