#!/bin/sh
# B57a step 4 — deploy handoff (git-as-seam; CI never calls `argocd sync`). For every image that built, bump its
# tag in the tracked manifests, push a branch, and open ONE PR against main. YOU merge it → Argo reconciles → rollout.
# Runs in a git+curl image from the repo root. Needs $GITHUB_TOKEN (fine-grained PAT: Contents:write + Pull requests:write on edtbl76/weyland-lab).
# Input: $BUMPS = "image<TAB>newtag<TAB>manifests"  (from build-images.sh)
set -eu

PLATFORM="${PLATFORM:-nodes/mother/lab/weyland-platform}"   # overridable so the test can bump a scratch manifest
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
CHANGED=""   # ONLY the manifests we bumped — the exact, and only, paths this commit may carry

# rewrite each tracked manifest's image tag to the new one
while IFS="$(printf '\t')" read -r image newtag manifests; do
  [ -n "$image" ] || continue
  IMAGES="${IMAGES} ${image}"
  for m in $manifests; do
    f="${PLATFORM}/${m}"
    [ -f "$f" ] || { echo "[handoff] WARN missing manifest ${f} — skipping"; continue; }
    sed -i -E "s#(${REG}/${image}):[A-Za-z0-9._-]+#\1:${newtag}#g" "$f"
    CHANGED="${CHANGED} ${f}"
    echo "[handoff] ${m} → ${image}:${newtag}"
  done
done < "$BUMPS"

git config user.email "ci@weyland.lab"
git config user.name  "weyland-ci"
git checkout -b "$BRANCH"
# Stage ONLY the manifests we bumped — NEVER `git commit -a`. `-a` sweeps in every OTHER dirty tracked
# file the pipeline left behind (the coverage ratchet's baseline row, a regenerated `.coverage` data
# file, …), which makes the bump PR non-tags-only and aborts ship-images.sh at FR2.1. Found 2026-09-01:
# a bump that had added python tests carried `.coverage` + a coverage-baseline bump into PR #61 and the
# ship stopped at FR2.1. Scoping the add to exactly what we changed fixes the whole class at the root.
# shellcheck disable=SC2086 # CHANGED is a space-joined list of repo paths (no spaces) — intentional split
[ -n "$CHANGED" ] && git add -- $CHANGED
git commit -m "ci: bump${IMAGES} to ${NEWTAG}"

# push the branch (token in the URL, never logged)
#
# THE BRANCH IS NAMED FROM THE SHA, so any re-run of the same commit finds its own branch already on
# origin — and `git push HEAD:$BRANCH` is then a NON-FAST-FORWARD even when the file content is
# identical, because re-committing the same tree produces a different commit object. git rejects it,
# `set -eu` kills the step, and the old `2>/dev/null` threw the reason away.
#
# Seen live 2026-08-24: run #26 pushed ci/image-bump-dab283e9 and opened PR #36; the nightly cron #27
# rebuilt the SAME sha six hours later, produced 058b4bd against origin's 89fa700, and died here. Its
# log simply ends at "5 files changed" — no error, no clue. It would have failed every night until
# PR #36 merged.
REMOTE="https://x-access-token:${GITHUB_TOKEN}@github.com/${REPO}.git"
push_needed="yes"
remote_sha=""

if remote_line="$(git ls-remote --exit-code --heads "$REMOTE" "$BRANCH" 2>/dev/null)"; then
  remote_sha="$(printf '%s\n' "$remote_line" | awk 'NR==1{print $1}')"
  echo "[handoff] branch ${BRANCH} is already on origin — comparing content"
  if git fetch -q "$REMOTE" "$BRANCH" >/dev/null 2>&1; then
    # Compare TREES, not commits. Same tree = this exact work is already published, and re-pushing a
    # fresh commit of identical content would only churn the open PR.
    remote_tree="$(git rev-parse 'FETCH_HEAD^{tree}' 2>/dev/null || echo unknown-remote)"
    local_tree="$(git rev-parse 'HEAD^{tree}' 2>/dev/null || echo unknown-local)"
    if [ "$remote_tree" = "$local_tree" ]; then
      echo "[handoff] identical content already pushed — skipping push, verifying the PR below"
      push_needed="no"
    else
      # Content genuinely differs for the same sha, which happens when a previous run built a
      # different SET of images (a partial build). This run is the newer, fuller answer.
      echo "[handoff] origin's copy of ${BRANCH} differs from this build — replacing it"
    fi
  else
    echo "[handoff] could not fetch ${BRANCH} to compare — will attempt a lease-guarded push" >&2
  fi
fi

if [ "$push_needed" = "yes" ]; then
  # Lease-guarded rather than a bare --force: if origin moved since the ls-remote above, the push is
  # refused instead of silently discarding whatever landed there.
  if [ -n "$remote_sha" ]; then
    push_out="$(git push --force-with-lease="${BRANCH}:${remote_sha}" "$REMOTE" "HEAD:${BRANCH}" 2>&1)" || push_rc=$?
  else
    push_out="$(git push "$REMOTE" "HEAD:${BRANCH}" 2>&1)" || push_rc=$?
  fi
  if [ "${push_rc:-0}" -ne 0 ]; then
    # The reason reaches the operator. Discarding it is why #27 was undiagnosable from its own log.
    echo "[handoff] push of ${BRANCH} FAILED (exit ${push_rc}): ${push_out}" >&2
    exit 1
  fi
  echo "[handoff] pushed branch ${BRANCH}"
fi

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
