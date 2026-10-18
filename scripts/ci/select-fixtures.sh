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

# --plan (2026-10-18): print RUN_FIXTURES / FIXTURE_LANES / GOLDEN_PATH_ONLY as eval-safe assignments instead of 0/1.
# FIXTURE_LANES '' = every lane (the full matrix), 'none' = no lane, else the lane keys (test-<key>/scan-<key>) to run.
PLAN=0
[ "${1:-}" = "--plan" ] && PLAN=1
emit_run_all() {
  if [ "$PLAN" -eq 1 ]; then printf "RUN_FIXTURES=1\nFIXTURE_LANES=''\nGOLDEN_PATH_ONLY=''\n"; else echo "1"; fi
  exit 0
}

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
CHANGED="$changed" MANIFEST="$MANIFEST" WP_BASE="$WP_BASE" WP_HEAD="$WP_HEAD" PLAN="$PLAN" ROOT="$ROOT" \
  LIST_ROOTS_CMD="${SELECT_LIST_ROOTS_CMD:-bash $ROOT/scripts/run-lang-tests.sh}" python3 - <<'PY' || emit_run_all
import os, re, shlex, subprocess, sys
PLAN = os.environ.get("PLAN") == "1"
FULL = "RUN_FIXTURES=1\nFIXTURE_LANES=''\nGOLDEN_PATH_ONLY=''"

def emit(decision, lanes="", paths=""):
    """0/1 in the classic mode; three eval-safe assignments in --plan mode."""
    if not PLAN:
        print(decision)
    elif decision == "0":
        print("RUN_FIXTURES=0\nFIXTURE_LANES=''\nGOLDEN_PATH_ONLY=''")
    else:
        print(f"RUN_FIXTURES=1\nFIXTURE_LANES='{lanes}'\nGOLDEN_PATH_ONLY='{paths}'")
    sys.exit(0)

try:
    import yaml
except Exception:
    emit("1")                                     # no pyyaml → cannot read manifest → run all
try:
    doc = yaml.safe_load(open(os.environ["MANIFEST"], encoding="utf-8")) or {}
except Exception:
    emit("1")                                     # unparseable manifest → run all
prefixes = [p for p in (doc.get("fixture_trigger_paths") or []) if p]
if not prefixes:
    emit("1")                                     # no trigger paths declared → cannot be lean → run all
changed = [ln.strip() for ln in os.environ.get("CHANGED", "").splitlines() if ln.strip()]
if not changed:
    emit("1")                                     # EMPTY diff is AMBIGUOUS, not "nothing changed": run it
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

fixture_changes = []
for f in changed:
    if f == ".woodpecker.yml" and not woodpecker_touches_fixtures():
        continue                                  # only ungated steps changed: they run in a lean pipeline anyway
    if any(f.startswith(pre) for pre in prefixes):
        fixture_changes.append(f)
if not fixture_changes:
    emit("0")                                     # diff had changes, NONE under a fixture path → skip fixtures
if not PLAN:
    emit("1")                                     # a fixture/lane path changed → run the full matrix

# --plan: narrow ONLY when every fixture change is a golden path (golden-paths/<a>/<b>/...) or a .woodpecker.yml change
# confined to lane steps (test-<key>/scan-<key>) with the top level untouched — those keys run. A shared trigger (a
# runner, tests/lang/, the manifest, the smoke step, a top-level key, golden-paths/<file>) = full.
def changed_lane_keys():
    """Keys of the fixture lane steps .woodpecker.yml changed; None = something else changed (or cannot tell) → full."""
    old, new = fixture_view(os.environ.get("WP_BASE", "")), fixture_view(os.environ.get("WP_HEAD", ""))
    if old is None or new is None or old[0] != new[0]:
        return None
    by_name = lambda steps: {st.get("name"): st for st in steps}
    o, n = by_name(old[1]), by_name(new[1])
    keys = set()
    for name in set(o) | set(n):
        if o.get(name) == n.get(name):
            continue
        m = re.match(r"^(?:test|scan)-([a-z0-9-]+)$", str(name))
        if not m:
            return None                           # the smoke step (or an unknown gated step) changed → full
        keys.add(m.group(1))
    return keys

extra_lanes = set()
if ".woodpecker.yml" in fixture_changes:
    keys = changed_lane_keys() if os.environ.get("WP_BASE") else None
    if keys is None:
        emit("1")
    extra_lanes = keys
    fixture_changes = [f for f in fixture_changes if f != ".woodpecker.yml"]
gp_changes = [f for f in fixture_changes if f.startswith("golden-paths/") and len(f.split("/")) >= 4]
if len(gp_changes) != len(fixture_changes):
    emit("1")

def lane_table():
    """{lane key: {languages}} from the fixture-gated steps that run run-lang-(tests|scan).sh <lang>. None = cannot tell."""
    try:
        doc = yaml.safe_load(open(os.environ.get("WP_HEAD", ""), encoding="utf-8"))
    except Exception:
        return None
    table = {}
    for st in (doc or {}).get("steps") or []:
        if not isinstance(st, dict) or "RUN_FIXTURES" not in str(st.get("when", "")):
            continue
        m = re.match(r"^(?:test|scan)-([a-z0-9-]+)$", str(st.get("name", "")))
        langs = set(re.findall(r"run-lang-(?:tests|scan)\.sh\s+([a-z0-9-]+)", " ".join(map(str, st.get("commands") or []))))
        if m and langs:
            table.setdefault(m.group(1), set()).update(langs)
    return table or None

def lang_roots(langs):
    """{lang: [repo-relative roots]} — the lane's own discovery (run-lang-tests.sh <lang> --list-roots). None = failed."""
    seam = os.environ.get("SELECT_LANG_ROOTS")
    roots = {}
    if seam is not None:
        for ln in seam.splitlines():
            if ln.strip():
                lang, _, path = ln.strip().partition(" ")
                roots.setdefault(lang, []).append(path.strip().rstrip("/"))
        return roots
    root = os.environ["ROOT"].rstrip("/") + "/"
    for lang in sorted(langs):
        try:
            r = subprocess.run(shlex.split(os.environ["LIST_ROOTS_CMD"]) + [lang, "--list-roots"],
                               capture_output=True, text=True, timeout=120)
        except Exception:
            return None
        found = [ln.split(":", 1)[1].strip() for ln in r.stdout.splitlines() if ln.startswith(("fixture:", "project:"))]
        if r.returncode != 0 or not any(ln.startswith("fixture:") for ln in r.stdout.splitlines()):
            return None                           # a lane that cannot say what it tests → cannot narrow
        roots[lang] = [p[len(root):] if p.startswith(root) else p for p in found]
    return roots

table = lane_table()
roots = lang_roots(set().union(*table.values())) if table else None
if not table or roots is None:
    emit("1")
lanes, paths = set(extra_lanes), set()
for f in gp_changes:
    for key, langs in table.items():
        if any(f.startswith(r + "/") for lang in langs for r in roots.get(lang, [])):
            lanes.add(key)
    gp = "/".join(f.split("/")[1:3])
    if os.path.isfile(os.path.join(os.environ["ROOT"], "golden-paths", gp, "Dockerfile")):
        paths.add(gp)
tok = re.compile(r"^[a-z0-9/._-]+$")
if not all(tok.match(x) for x in lanes | paths):
    emit("1")                                     # never print an unsafe token into an eval'd assignment
emit("1", " ".join(sorted(lanes)) or "none", " ".join(sorted(paths)))
PY
