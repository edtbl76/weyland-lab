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
#   scripts/sync-golden-shared.sh --check   exit 0 all copies match · 1 a copy drifted or is missing (named) ·
#                                           2 shared code that no path opts in to (checking nothing is not a pass)
# Runs as a repo guard (--check). Tests: scripts/tests/sync-golden-shared.bats.
set -uo pipefail

root="${REPO_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
mode="${1:-write}"
shared="$root/golden-paths-shared"
drift=0 copies=0

expected() { # expected <lang> <relative file>: the copy's exact content
  printf '# GENERATED from golden-paths-shared/%s/%s by scripts/sync-golden-shared.sh: edit the source, not this copy.\n' "$1" "$2"
  cat "$shared/$1/$2"
}

for langdir in "$shared"/*/; do
  [ -d "$langdir" ] || continue
  lang="$(basename "$langdir")"
  mapfile -t files < <(cd "$langdir" && find . -type f -not -path '*/__pycache__/*' -not -name '*.pyc' \
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
  done
done

if [ "$mode" = --check ]; then
  [ "$drift" -eq 0 ] || exit 1
  echo "sync-golden-shared: OK, $copies shared file copy(ies) in sync"
else
  echo "sync-golden-shared: wrote $copies shared file copy(ies)"
fi
