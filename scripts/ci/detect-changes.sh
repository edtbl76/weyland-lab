#!/bin/sh
# B57a step 1 — detect which weyland images need rebuilding.
# Each tag-following manifest already carries `registry.weyland.lab/<img>:git-<oldsha>`. We diff the image's build
# context from <oldsha> to HEAD; changed → rebuild at git-<HEADsha>. An image not yet on a git-* tag (first
# migration off :vN) always builds. Writes a build plan the BuildKit step consumes.
# Runs from the repo root in a git-capable image. Output: $PLAN = "image<TAB>context<TAB>newtag<TAB>manifests".
set -eu

# EVERY input is anchored to the git toplevel, never to the caller's cwd.
#
# 2026-08-24: `bash scripts/ship-images.sh` was run from nodes/.../tofu/port while a real
# dbt-core/sqlparse bump sat committed on main. TSV and PLATFORM were relative, so the TSV simply
# was not there — and the read loop below is the LAST command in a pipeline, so `grep`'s exit 2 and
# its "No such file or directory" were both discarded: a `while` over empty input returns 0. The
# caller saw exit 0 plus an empty plan and reported "✓ nothing to ship". Three images were stale.
#
# Same class as the shallow-clone bug described above — an error read as data — except this time it
# read as "no work", which is the direction that ships nothing while looking successful.
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[ -n "$ROOT" ] || {
  echo "[detect] ❌ cannot resolve the repo root (git rev-parse --show-toplevel failed) — refusing to report 'nothing to build'" >&2
  exit 1
}

# Resolve PLAN to an absolute path BEFORE the cd, so a caller's relative path still lands where the
# caller meant it to. In CI cwd is already the repo root, so this is a no-op there.
PLAN="${PLAN:-.ci-build-plan}"
case "$PLAN" in
  /*) : ;;
  *) PLAN="$(pwd)/$PLAN" ;;
esac

cd "$ROOT" || {
  echo "[detect] ❌ cannot enter repo root ${ROOT} — refusing to report 'nothing to build'" >&2
  exit 1
}

PLATFORM="nodes/mother/lab/weyland-platform"
TSV="scripts/ci/images.tsv"
: > "$PLAN"

# Both checks run HERE, up front, where a failure is still visible. Down in the read loop the exit
# status belongs to the `while`, and can never speak for the greps feeding it.
[ -r "$TSV" ] || {
  echo "[detect] ❌ image manifest not readable: ${TSV} — refusing to report 'nothing to build'" >&2
  exit 1
}
rows="$(grep -v '^[[:space:]]*#' "$TSV" | grep -v '^[[:space:]]*$' | grep -c '' || true)"
[ "${rows:-0}" -gt 0 ] || {
  echo "[detect] ❌ no image rows in ${TSV} — refusing to report 'nothing to build'" >&2
  exit 1
}

NEWSHA="$(git rev-parse --short=8 HEAD)"
NEWTAG="git-${NEWSHA}"
echo "[detect] HEAD=${NEWSHA} → candidate tag ${NEWTAG}"

# CHANGE DETECTION NEEDS HISTORY, AND WOODPECKER CLONES SHALLOW.
# Until 2026-08-22 this script ran `git diff <oldsha> HEAD -- <path> 2>/dev/null` inside a shallow
# clone, where <oldsha> is not present. git exits non-zero with "unknown revision"; the redirect ate
# the message and the `if` read the failure as "changed" — so EVERY image rebuilt on EVERY run and
# nobody could tell. Detection had never once worked in CI; it only looked right locally, where the
# clone has full history. (Fourth instance in one day of an error being read as data.)
if [ "$(git rev-parse --is-shallow-repository 2>/dev/null)" = "true" ]; then
  echo "[detect] shallow clone — deepening so the old shas are reachable"
  git fetch --unshallow --quiet 2>/dev/null \
    || git fetch --depth=200 --quiet 2>/dev/null \
    || echo "[detect] WARN could not deepen; detection will degrade to build-everything (announced per image)"
fi

# strip comments/blank lines; read TAB-separated rows
grep -v '^[[:space:]]*#' "$TSV" | grep -v '^[[:space:]]*$' | while IFS="$(printf '\t')" read -r image context manifests; do
  [ -n "$image" ] || continue
  # optional allowlist for scoped/validation runs: ONLY="img1 img2" builds only those (SoT tsv stays intact)
  if [ -n "${ONLY:-}" ]; then
    case " $ONLY " in *" $image "*) : ;; *) continue ;; esac
  fi
  # context dir = part before "::" (Dockerfile spec), repo-relative under the platform dir
  ctxdir="${context%%::*}"
  path="${PLATFORM}/${ctxdir}"

  # current tag from the FIRST manifest (lockstep → all equal); may be absent on a brand-new image
  first_manifest="$(printf '%s' "$manifests" | awk '{print $1}')"
  oldtag=""
  if [ -n "$first_manifest" ] && [ -f "${PLATFORM}/${first_manifest}" ]; then
    oldtag="$(grep -oE "registry\.weyland\.lab/${image}:[A-Za-z0-9._-]+" "${PLATFORM}/${first_manifest}" | head -n1 | sed "s#.*:##")"
  fi

  build="no"
  case "$oldtag" in
    git-*)
      oldsha="${oldtag#git-}"
      # THREE outcomes, not two. "I cannot compare" is not "it changed" — conflating them is what hid
      # the shallow-clone bug for months. Build in that case (safe), but SAY it is a degraded answer.
      if ! git cat-file -e "${oldsha}^{commit}" 2>/dev/null; then
        echo "[detect] ${image}: ⚠ ${oldtag} unreachable in this clone — BUILDING, but this is DEGRADED"
        echo "[detect] ${image}:   detection, not an observed change. Deepen the clone to fix."
        build="yes"
      elif git diff --quiet "${oldsha}" HEAD -- "$path" 2>/dev/null; then
        echo "[detect] ${image}: unchanged since ${oldtag} — skip"
      else
        echo "[detect] ${image}: context ${ctxdir} changed since ${oldtag} — BUILD"
        build="yes"
      fi
      ;;
    "")
      echo "[detect] ${image}: no current tag found (new image) — BUILD"
      build="yes"
      ;;
    *)
      echo "[detect] ${image}: on non-git tag '${oldtag}' (first migration) — BUILD"
      build="yes"
      ;;
  esac

  if [ "$build" = "yes" ]; then
    printf '%s\t%s\t%s\t%s\n' "$image" "$context" "$NEWTAG" "$manifests" >> "$PLAN"
  fi
done

n="$(wc -l < "$PLAN" | tr -d ' ')"
echo "[detect] ${n} image(s) to build:"
cat "$PLAN" || true
[ "$n" -gt 0 ] || echo "[detect] nothing to build — the build/handoff steps will no-op."
