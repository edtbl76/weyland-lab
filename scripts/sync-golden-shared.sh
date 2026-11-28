#!/usr/bin/env bash
# sync-golden-shared.sh [--check] — one source for code every golden path of a language shares (B261).
#
# Each golden path must stay self-contained: golden-path-smoke builds its image from its own directory and
# new-service.sh copies only that directory. So code the paths of one language share (B163's integration tier: the
# ItemStore, the real-backend adapters and their tests) lives ONCE in golden-paths-shared/<lang>/ and is copied into
# every path of that language that opts in with an empty `.golden-shared` marker. Each copy's first line says it is
# generated and names its source. Owner decision 2026-11-25: "One source, synced copies".
#
#   scripts/sync-golden-shared.sh           write every copy
#   scripts/sync-golden-shared.sh --check   exit 0 all copies match · 1 a copy drifted, is missing or is an orphan
#                                           (its source was renamed or removed; a write deletes it), named ·
#                                           2 shared code that no path opts in to (checking nothing is not a pass)
# Runs as a repo guard (--check). Tests: scripts/tests/sync-golden-shared.bats.
set -uo pipefail

root="${REPO_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
mode="${1:-write}"
shared="$root/golden-paths-shared"
drift=0 copies=0

# The header is a comment in the copy's own language: `#` is not a comment in JavaScript/TypeScript (B262).
comment_for() { case "$1" in *.js|*.cjs|*.mjs|*.ts) echo '//' ;; *) echo '#' ;; esac; }

expected() { # expected <lang> <relative file>: the copy's exact content
  printf '%s GENERATED from golden-paths-shared/%s/%s by scripts/sync-golden-shared.sh: edit the source, not this copy.\n' \
    "$(comment_for "$2")" "$1" "$2"
  cat "$shared/$1/$2"
}

for langdir in "$shared"/*/; do
  [ -d "$langdir" ] || continue
  lang="$(basename "$langdir")"
  mapfile -t files < <(cd "$langdir" && find . -type f -not -path '*/__pycache__/*' -not -name '*.pyc' -not -path '*/node_modules/*' \
                                             -not -name 'README.md' | sed 's|^\./||' | sort)
  [ "${#files[@]}" -gt 0 ] || continue
  targets=()
  for marker in "$root/golden-paths/$lang"/*/.golden-shared; do
    [ -f "$marker" ] && targets+=("$(dirname "$marker")")
  done
  if [ "${#targets[@]}" -eq 0 ]; then
    echo "sync-golden-shared: golden-paths-shared/$lang has shared code but no golden path opts in (.golden-shared)" >&2
    exit 2
  fi
  for target in "${targets[@]}"; do
    for f in "${files[@]}"; do
      copies=$((copies + 1))
      dest="$target/$f" rel="${target#"$root"/}/$f"
      if [ "$mode" = --check ]; then
        if ! expected "$lang" "$f" | cmp -s - "$dest"; then
          echo "DRIFT: $rel differs from golden-paths-shared/$lang/$f (run scripts/sync-golden-shared.sh)" >&2
          drift=1
        fi
      else
        mkdir -p "$(dirname "$dest")"
        expected "$lang" "$f" > "$dest"
      fi
    done
    # Orphans (B262): a copy whose header names a source that no longer exists (renamed or removed). Only a file
    # this script generated (its first line is the header) is ever considered; a hand-written file is never touched.
    while IFS= read -r copy; do
      src="$(head -n 1 -- "$copy" 2>/dev/null | sed -nE 's~^(#|//) GENERATED from golden-paths-shared/'"$lang"'/([^ ]+) by scripts/sync-golden-shared\.sh: edit the source, not this copy\.$~\2~p')"
      [ -n "$src" ] && [ ! -f "$shared/$lang/$src" ] || continue
      if [ "$mode" = --check ]; then
        echo "ORPHAN: ${copy#"$root"/} names golden-paths-shared/$lang/$src, which no longer exists (run scripts/sync-golden-shared.sh)" >&2
        drift=1
      else
        rm -f -- "$copy" && echo "sync-golden-shared: removed orphan ${copy#"$root"/}"
      fi
    done < <(find "$target" \( -name node_modules -o -name dist \) -prune -o -type f -print)   # portable: no GNU grep -r flags
  done
done

if [ "$mode" = --check ]; then
  [ "$drift" -eq 0 ] || exit 1
  echo "sync-golden-shared: OK, $copies shared file copy(ies) in sync"
else
  echo "sync-golden-shared: wrote $copies shared file copy(ies)"
fi
