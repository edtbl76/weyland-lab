#!/usr/bin/env bash
# check-tofu-fmt.sh — every OpenTofu directory in the repo must pass `tofu fmt -check`.
#
# WHY THIS EXISTS: on 2026-09-24, 7 files across tofu/github, tofu/port and tofu/proxmox had drifted from
# canonical format (27 whitespace-only lines) and nothing in CI would ever have said so. Formatting drift is
# harmless on its own, but it buries real changes in noise: the next edit to repo.tf re-aligned 26 lines to
# change one. Runs in the `repo-guards` CI step (tofu is `apk add opentofu` there).
#
# DISCOVERY: every directory under nodes/ holding a *.tf file (all OpenTofu in this repo lives there),
# skipping provider caches (.terraform/). Override with TOFU_DIRS="<dir> <dir> ..." (the bats seam).
#
# `tofu fmt -check` contract (observed on OpenTofu 1.12.5): 0 = formatted, 3 = needs formatting (prints the
# file names), 2 = does not parse (prints an Error). A parse error is the guard failing to judge, not a
# formatting finding, so it is exit 2 — the same split every guard here keeps.
#
# EXIT: 0 = all formatted · 1 = a directory needs `tofu fmt` · 2 = guard broken (no tofu, no directories,
# a missing directory, or a parse error). Checking nothing is never a pass.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

command -v tofu >/dev/null 2>&1 || { echo "❌ guard broken: tofu not found on PATH" >&2; exit 2; }

if [ -n "${TOFU_DIRS+x}" ]; then
  read -r -a dirs <<<"$TOFU_DIRS"
else
  # No `find -printf`: CI runs busybox find (Alpine), which lacks it. Strip the file name with sed instead.
  mapfile -t dirs < <(find "$ROOT/nodes" -name '*.tf' -not -path '*/.terraform/*' | sed 's|/[^/]*$||' | sort -u)
fi
[ "${#dirs[@]}" -gt 0 ] || { echo "❌ guard broken: no OpenTofu directories found to check" >&2; exit 2; }

fail=0
for d in "${dirs[@]}"; do
  [ -d "$d" ] || { echo "❌ guard broken: OpenTofu directory $d does not exist" >&2; exit 2; }
  rel="${d#"$ROOT"/}"
  rc=0
  out="$(tofu -chdir="$d" fmt -check -no-color 2>&1)" || rc=$?
  case "$rc" in
    0) echo "  ✓ $rel" ;;
    3) echo "  ❌ $rel — needs formatting: $(echo "$out" | tr '\n' ' ')"
       fail=1 ;;
    *) echo "$out" >&2
       echo "❌ guard broken: tofu fmt could not judge $rel (exit $rc — see the error above)" >&2
       exit 2 ;;
  esac
done

if [ "$fail" -ne 0 ]; then
  echo "" >&2
  echo "❌ OpenTofu formatting drift. Fix: cd <dir> && tofu fmt   (whitespace only — confirm with git diff -w)" >&2
  exit 1
fi
echo "OK — ${#dirs[@]} OpenTofu directories pass tofu fmt -check."
