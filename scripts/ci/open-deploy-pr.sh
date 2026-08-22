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

API="https://api.github.com/repos/${REPO}"
OWNER="${REPO%%/*}"

# Status and body together, so the two are never confused. `-sf` was the defect: it collapsed EVERY
# non-2xx into one exit code, so a 422 (duplicate head — fine) and a 500 (GitHub is broken — not
# fine) took the same branch, and that branch exited 0. A green pipeline that opened no PR is
# constraint C9, and it is the whole reason ship-images.sh has to re-verify from the outside.
resp="$(curl -s -w '\n%{http_code}' -X POST \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  "${API}/pulls" \
  -d "$payload" 2>/dev/null)"
code="$(printf '%s' "$resp" | tail -n1)"
body="$(printf '%s' "$resp" | sed '$d')"

case "$code" in
  201)
    echo "[handoff] PR opened: $(printf '%s' "$body" | grep -oE '"html_url"[^,]*' | head -n1 | sed 's/.*: *//; s/"//g')"
    ;;
  422)
    # KEPT ON PURPOSE (FR3.3): a re-run legitimately hits a duplicate head, and deleting this branch
    # would break that. What changes is that "already open" is now checked instead of assumed —
    # an unverified claim that leaves the step green is the failure mode, not the tolerance itself.
    echo "[handoff] 422 from PR create — a PR for ${BRANCH} may already be open; verifying."
    lresp="$(curl -s -w '\n%{http_code}' \
      -H "Authorization: Bearer ${GITHUB_TOKEN}" \
      -H "Accept: application/vnd.github+json" \
      "${API}/pulls?head=${OWNER}:${BRANCH}&state=open" 2>/dev/null)"
    lcode="$(printf '%s' "$lresp" | tail -n1)"
    lbody="$(printf '%s' "$lresp" | sed '$d')"
    if [ "$lcode" != "200" ]; then
      echo "[handoff] could not verify open PRs for ${BRANCH} (HTTP ${lcode}) — failing rather than reporting a green step." >&2
      exit 1
    fi
    case "$lbody" in
      *'"number"'*) echo "[handoff] confirmed: a PR for ${BRANCH} is already open." ;;
      *)
        echo "[handoff] no open PR for ${BRANCH} exists — the 422 was not a duplicate. FAILING." >&2
        exit 1
        ;;
    esac
    ;;
  *)
    echo "[handoff] PR create failed with HTTP ${code}: $(printf '%s' "$body" | head -c 300)" >&2
    exit 1
    ;;
esac
