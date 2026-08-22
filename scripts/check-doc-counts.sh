#!/usr/bin/env bash
# Documented-count drift guard. Asserts that counts hardcoded in docs PROSE match what the
# repository actually contains.
#
# WHY THIS EXISTS: on 2026-08-21 the Argo CD application count was found stated THREE
# different stale ways across seven files -- "onboarded (28)" in docs/runbooks/argocd.md,
# "28 apps" in docs/platform-map.html and docs/demos/deploy.md, "59 apps" in docs/api.md,
# docs/hosts.md and docs/arch.md, "29 apps"/"25 apps" in docs/concepts/application-catalog.md
# -- against 78 actual Application documents. None agreed with each other or with reality.
#
# WHY THE EXISTING GUARDS MISSED IT:
#   - scripts/check-app-registry.sh compares Argo manifests against applications.yaml, i.e.
#     STRUCTURE vs STRUCTURE. A number typed into a sentence is invisible to it.
#   - The Definition of Done's pillar-1 "relevance sweep" DOES mandate re-auditing every
#     docs section every batch, but it is a human read. A page saying "28 apps onboarded"
#     reads as perfectly relevant; nothing about it looks stale. Only comparing it to the
#     cluster reveals it, and nobody does that per number, per batch, across seven files.
#
# THE UNDERLYING PROBLEM: a number typed into prose has no owner. Nothing regenerates it and
# nothing checks it. This guard gives it an owner.
#
# Run from anywhere in the repo. Exit 1 (+ every mismatching file:line) on drift, 0 when clean.
set -euo pipefail

here="$(cd "$(dirname "$0")/.." && pwd)"
argo_dir="$here/nodes/mother/lab/weyland-platform/k8s/argocd"

command -v python3 >/dev/null 2>&1 || { echo "❌ python3 not found on PATH" >&2; exit 1; }

# --- Truth: distinct Argo CD Application names, counted the same way check-app-registry.sh
# does (applications/*.yaml PLUS the parent dir, so the app-of-apps root is included). ---
ARGO_APPS="$(python3 - "$argo_dir" <<'PY'
import sys, glob, os, yaml
d = sys.argv[1]
names = set()
for f in glob.glob(os.path.join(d, "applications", "*.yaml")) + glob.glob(os.path.join(d, "*.yaml")):
    for doc in yaml.safe_load_all(open(f)):
        if isinstance(doc, dict) and doc.get("kind") == "Application":
            n = doc.get("metadata", {}).get("name")
            if n:
                names.add(n)
print(len(names))
PY
)"

echo "→ truth: ${ARGO_APPS} distinct Argo CD Applications"

fail=0

# --- Claimed counts.
#
# "apps" is OVERLOADED in this repo and a naive `[0-9]+ apps` match produces false
# positives that would get this guard ignored. Three things are deliberately NOT matched:
#
#   1. HISTORICAL RECORDS -- docs/backlog.md and docs/completeness-audit.md are append-only
#      and their older entries are SUPPOSED to say what was true when written
#      (completeness-audit.md is a dated 2026-06-26 snapshot).
#   2. THE B82 APPLICATION TAXONOMY -- docs/concepts/application-catalog.md says
#      "29 apps"/"25 apps" for its data-plausible and pure-compute subsets. Those count
#      entries in services/weyland-dagster/weyland_pipeline/applications.yaml, a DIFFERENT
#      set from Argo Applications (64 `applications:` + 40 `excluded:` at this commit).
#      Flagging them against the Argo number would be wrong.
#   3. SUBSET STATEMENTS -- e.g. docs/arch.md's "6 apps cut over" (Keycloak SSO rollout).
#
# Matching strategy: flag EVERY "<N> apps" by default and subtract a short, documented
# exclusion list. The alternative -- requiring Argo keywords near the number -- was tried
# first and produced FALSE NEGATIVES (it silently dropped real drift in
# docs/architecture/weyland.likec4 "GitOps reconcile (28 apps)" and
# docs/demos/application-taxonomy.md "(72 apps)"). A guard that misses drift is worse than
# one that occasionally over-reports, so the default is to flag and the exceptions are
# explicit -- the same shape as check-app-registry.sh's ALIAS map.
claims="$(grep -rnoE "onboarded \([0-9]+\)|\b[0-9]{1,3} (Argo )?apps?\b" "$here/docs" 2>/dev/null || true)"

filtered=""
while IFS= read -r hit; do
  [ -n "$hit" ] || continue
  hf="${hit%%:*}"; rest="${hit#*:}"; hn="${rest%%:*}"

  # (1) Append-only historical records: their older entries are SUPPOSED to be stale.
  case "$hf" in
    */docs/backlog.md|*/docs/completeness-audit.md) continue ;;
  esac

  # (2) The B82 application TAXONOMY is a different set from Argo Applications. Its counts
  #     come from services/weyland-dagster/weyland_pipeline/applications.yaml
  #     (`applications:` + `excluded:`), not from k8s/argocd/. Never compare it to Argo.
  case "$hf" in
    */docs/concepts/application-catalog.md) continue ;;
  esac

  ctx="$(sed -n "${hn}p" "$hf" 2>/dev/null || true)"

  # (3) Documented SUBSET statements -- a count of some apps, not all of them.
  #     "6 apps cut over" = the Keycloak SSO rollout subset (docs/arch.md).
  if printf '%s' "$ctx" | grep -qiE "cut over|redistributed"; then continue; fi

  filtered="${filtered}${hit}"$'\n'
done <<< "$claims"
claims="$filtered"

if [ -n "$claims" ]; then
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    claimed="$(printf '%s' "$line" | grep -oE '[0-9]+' | tail -1)"
    if [ "$claimed" != "$ARGO_APPS" ]; then
      echo "❌ ${line}   → claims ${claimed}, actual ${ARGO_APPS}" >&2
      fail=1
    fi
  done <<< "$claims"
fi

if [ "$fail" -ne 0 ]; then
  echo "" >&2
  echo "❌ documented Argo application counts do not match reality (${ARGO_APPS})." >&2
  echo "   Fix the prose, or stop hardcoding the count in that sentence." >&2
  exit 1
fi

echo "✓ documented Argo application counts agree with reality (${ARGO_APPS})"
