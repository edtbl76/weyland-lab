#!/bin/sh
# B57a step 1 — detect which weyland images need rebuilding.
# Each tag-following manifest already carries `registry.weyland.lab/<img>:git-<oldsha>`. We diff the image's build
# context from <oldsha> to HEAD; changed → rebuild at git-<HEADsha>. An image not yet on a git-* tag (first
# migration off :vN) always builds. Writes a build plan the BuildKit step consumes.
# Runs from the repo root in a git-capable image. Output: $PLAN = "image<TAB>context<TAB>newtag<TAB>manifests".
set -eu

PLATFORM="nodes/mother/lab/weyland-platform"
TSV="scripts/ci/images.tsv"
PLAN="${PLAN:-.ci-build-plan}"
: > "$PLAN"

NEWSHA="$(git rev-parse --short=8 HEAD)"
NEWTAG="git-${NEWSHA}"
echo "[detect] HEAD=${NEWSHA} → candidate tag ${NEWTAG}"

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
      if git diff --quiet "${oldsha}" HEAD -- "$path" 2>/dev/null; then
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
