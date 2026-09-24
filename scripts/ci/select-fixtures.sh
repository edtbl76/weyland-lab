#!/usr/bin/env bash
# select-fixtures.sh (B177) — decide whether CI's fixture-language lanes must run this pipeline.
#
# Prints exactly "1" (run the full fixture matrix) or "0" (skip fixtures — only production lanes run),
# for the woodpecker trigger command to pass as `--var RUN_FIXTURES=<n>`. Each fixture lane in
# .woodpecker.yml gates on `RUN_FIXTURES != "0"` (the proven `when: evaluate` pattern), so an UNSET var
# (a plain manual run, or the nightly cron) reads as "" != "0" → runs — the full matrix stays the safe
# default; leanness is this script's explicit opt-in.
#
# FAIL-CLOSED — "0" (skip) is emitted ONLY on a git diff that SUCCEEDED and matched none of the
# manifest's fixture_trigger_paths. Every other outcome prints "1":
#   - no readable manifest (ci-langs.yaml)         - git absent, or the diff command failed
#   - manifest unparseable / no trigger paths       - any change under a fixture_trigger_path prefix
# This is the project.md c14 rule: an absent/errored result must never stand for "nothing changed".
#
# TEST SEAM: set SELECT_CHANGED_FILES (newline-separated paths) to bypass git entirely and feed the
# decision a fixed changed-file list. CI_LANGS_FILE overrides the manifest path; SELECT_BASE the diff base.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MANIFEST="${CI_LANGS_FILE:-$ROOT/ci-langs.yaml}"
BASE="${SELECT_BASE:-origin/main}"

emit_run_all() { echo "1"; exit 0; }

# 1. The manifest must be readable — without it we cannot know what "lean" means, so run everything.
[ -r "$MANIFEST" ] || emit_run_all

# 2. Gather the changed files. Test seam first; otherwise from git, failing closed on any git trouble.
if [ -n "${SELECT_CHANGED_FILES+x}" ]; then
  changed="$SELECT_CHANGED_FILES"
else
  command -v git >/dev/null 2>&1 || emit_run_all
  # Three-dot = changes since the merge-base with BASE (what this branch adds), plus the working tree
  # (staged + unstaged) so a local pre-push run judges what is actually about to ship. A FAILED diff
  # (no remote, detached, shallow-without-base) fails closed to run-all — never an empty "nothing changed".
  base_diff="$(git -C "$ROOT" diff --name-only "$BASE"...HEAD 2>/dev/null)" || emit_run_all
  changed="$(printf '%s\n%s\n%s\n' \
      "$base_diff" \
      "$(git -C "$ROOT" diff --name-only 2>/dev/null || true)" \
      "$(git -C "$ROOT" diff --name-only --cached 2>/dev/null || true)")"
fi

# 3. Decide. Python matches each changed file against the manifest's fixture_trigger_paths prefixes.
#    Any python trouble (missing python3, missing pyyaml, unparseable manifest, no prefixes) prints "1".
CHANGED="$changed" MANIFEST="$MANIFEST" python3 - <<'PY' || emit_run_all
import os, sys
try:
    import yaml
except Exception:
    print("1"); sys.exit(0)                       # no pyyaml → cannot read manifest → run all
try:
    doc = yaml.safe_load(open(os.environ["MANIFEST"], encoding="utf-8")) or {}
except Exception:
    print("1"); sys.exit(0)                       # unparseable manifest → run all
prefixes = [p for p in (doc.get("fixture_trigger_paths") or []) if p]
if not prefixes:
    print("1"); sys.exit(0)                       # no trigger paths declared → cannot be lean → run all
changed = [ln.strip() for ln in os.environ.get("CHANGED", "").splitlines() if ln.strip()]
for f in changed:
    if any(f.startswith(pre) for pre in prefixes):
        print("1"); sys.exit(0)                   # a fixture/lane path changed → run the full matrix
print("0")                                        # diff succeeded, matched nothing → skip fixtures
PY
