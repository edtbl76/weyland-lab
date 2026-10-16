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
#   - a .woodpecker.yml change whose fixture-gated steps or top-level keys differ, or whose base cannot be read
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

# 2b. .woodpecker.yml is compared by CONTENT, not by name (2026-10-16): only its fixture-gated steps and its top-level
#     keys can change what a fixture lane does. Pipeline #382 ran the whole matrix for hours because one line was added
#     to repo-guards, a step every lean run executes anyway. The base version is the merge-base copy; a missing one
#     (new file, git trouble) leaves the path empty and step 3 fails closed. TEST SEAMS: SELECT_WOODPECKER_BASE /
#     SELECT_WOODPECKER_HEAD name the two files directly.
WP_HEAD="${SELECT_WOODPECKER_HEAD:-$ROOT/.woodpecker.yml}"
WP_BASE="${SELECT_WOODPECKER_BASE:-}"
if [ -z "${SELECT_WOODPECKER_BASE+x}" ] && grep -qxF '.woodpecker.yml' <<<"$changed"; then
  WP_BASE="$(mktemp)"; trap 'rm -f "$WP_BASE"' EXIT
  if ! mb="$(git -C "$ROOT" merge-base "$BASE" HEAD 2>/dev/null)" \
     || ! git -C "$ROOT" show "$mb:.woodpecker.yml" > "$WP_BASE" 2>/dev/null; then
    rm -f "$WP_BASE"; WP_BASE=""
  fi
fi

# 3. Decide. Python matches each changed file against the manifest's fixture_trigger_paths prefixes.
#    Any python trouble (missing python3, missing pyyaml, unparseable manifest, no prefixes) prints "1".
CHANGED="$changed" MANIFEST="$MANIFEST" WP_BASE="$WP_BASE" WP_HEAD="$WP_HEAD" python3 - <<'PY' || emit_run_all
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
if not changed:
    print("1"); sys.exit(0)                       # EMPTY diff is AMBIGUOUS, not "nothing changed": run it
    #                                               after a push (HEAD == origin/main) and it is empty even
    #                                               though the push may have touched golden paths. Fail
    #                                               closed to the full matrix; "0" needs POSITIVE evidence
    #                                               of a non-fixture-only change. Run the selector BEFORE
    #                                               pushing (dirty tree) to get the lean signal.
def fixture_view(path):
    """The parts of a .woodpecker.yml that decide what a fixture lane does: every top-level key except `steps`, plus
    the steps whose `when` gates on RUN_FIXTURES (anchors resolved by the loader). None = cannot tell → trigger."""
    try:
        doc = yaml.safe_load(open(path, encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(doc, dict) or not isinstance(doc.get("steps"), list):
        return None
    gated = [s for s in doc["steps"] if isinstance(s, dict) and "RUN_FIXTURES" in str(s.get("when", ""))]
    if not gated:
        return None                               # no gated step at all: the gate was renamed or removed → trigger
    return ({k: v for k, v in doc.items() if k != "steps"}, gated)

def woodpecker_touches_fixtures():
    base, head = os.environ.get("WP_BASE", ""), os.environ.get("WP_HEAD", "")
    if not base or not head:
        return True
    old, new = fixture_view(base), fixture_view(head)
    return old is None or new is None or old != new

for f in changed:
    if f == ".woodpecker.yml" and not woodpecker_touches_fixtures():
        continue                                  # only ungated steps changed: they run in a lean pipeline anyway
    if any(f.startswith(pre) for pre in prefixes):
        print("1"); sys.exit(0)                   # a fixture/lane path changed → run the full matrix
print("0")                                        # diff had changes, NONE under a fixture path → skip fixtures
PY
