#!/usr/bin/env bash
# DoD Pillar 5 — backlog/Linear status reconciliation.
#
# WHY THIS EXISTS: Pillar 5 was the ONE pillar with nothing that could contradict the person filling
# it in. Every other pillar has a checker — `check-mermaid.sh`, `check-cron-freshness-budgets.sh`,
# the bats suite, eyes on a dashboard. Pillar 5 was prose in a checklist, so writing the tick WAS the
# work. On 2026-08-26 the B148 DoD recorded "5 OK — Linear EMA-207" while no Linear call had been
# made at all and the issue sat in Backlog; B143 had been open for two days after shipping.
#
# `CLAUDE.md` is explicit: the backlog is the ORDERED source of truth, Linear is STATUS. So the two
# documents make claims about each other, and until now nothing compared them.
#
# TWO CHECKS, both mechanically detectable:
#
#   A. A backlog entry marked DONE that names a Linear issue NOT in a terminal state.
#      Deliberately ONE-WAY: an issue closed in Linear while the backlog entry is still open is a
#      normal mid-flight state, not drift.
#   B. An OPEN Linear issue with no project. This workspace runs two products (Weyland Lab and
#      Stud.IO) on one team, and project assignment is what separates them — so an issue with no
#      project is invisible to BOTH filtered views while still counting in the team total. Found
#      EMA-186 and EMA-172 that way; the latter is High priority, was open since 2026-08-12, and
#      appeared in no "what's next" answer anyone asked.
#
#   usage: scripts/check-linear-sync.sh [--list]
#          --list   print every backlog->Linear ref and its verdict, exit 0
#
# INPUTS. Live mode needs a Linear personal API key (Settings -> Security & access -> New API key):
#
#   LINEAR_API_KEY        read from the environment, or from the gitignored scripts/.env
#   LINEAR_TEAM           team key, default EMA
#
# For testing (and offline runs) point this at a fixture instead — it skips the API entirely:
#
#   LINEAR_SNAPSHOT_JSON  {"EMA-207": {"stateType": "...", "state": "...", "project": "..."|null}}
#   BACKLOG_FILE          defaults to docs/backlog.md
#
# EXIT CODES are distinct on purpose. 1 = the estate has drift. 2 = the guard could not do its job.
# Conflating them means a missing token reads exactly like a clean backlog — and "checked nothing,
# found nothing" is the precise bug this whole family of guards exists to catch.
set -euo pipefail

BACKLOG_FILE="${BACKLOG_FILE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/docs/backlog.md}"
LINEAR_TEAM="${LINEAR_TEAM:-EMA}"

# --- the decision --------------------------------------------------------------------------------
#
# is_terminal <linear-stateType> -> 0 when the issue counts as closed.
#
# Linear's stateType enum, not its display NAME: a workspace can rename "Done" to anything, and this
# workspace already carries two started-type states (In Progress, In Review). FAILS CLOSED on an
# unknown value — a state nobody taught this function about must never silently count as finished.
is_terminal() { # is_terminal <stateType>
  case "${1-}" in
    completed|canceled|duplicate) return 0 ;;
    *)                            return 1 ;;
  esac
}

# --- parsing the backlog -------------------------------------------------------------------------
#
# backlog_refs <backlog-file> -> `<B-num>\t<EMA-id>\t<done|open>` per line.
#
# BOTH reference formats are matched: `Linear: EMA-207` and `[Linear EMA-46]`. Supporting only one
# silently halves coverage, and the unchecked half looks identical to the passing half.
#
# `(original entry)` headings are skipped. Closed items keep their superseded text inside <details>,
# and counting it would double every closed item and could resurrect a stale status.
backlog_refs() { # backlog_refs <backlog-file>
  local f="${1:?usage: backlog_refs <backlog-file>}"
  [ -r "$f" ] || { echo "FATAL: cannot read the backlog: $f" >&2; return 1; }
  python3 - "$f" <<'PY' || return 1
import re, sys
path = sys.argv[1]
lines = open(path, encoding="utf-8").read().split("\n")
REF = re.compile(r"(?:Linear:?\s*|\[Linear\s+)(EMA-\d+)")

# FIRST STATUS-OR-PRIORITY TOKEN WINS — do NOT just search the line for "DONE".
#
# The list entries are long (B60's is 1574 characters) and routinely narrate OTHER items' status
# inside themselves: `[B63, DONE 2026-08-19]`, `scorecards DONE (->B61)`. A bare `\bDONE\b` search
# read B63's status as B60's and reported drift on an item correctly open in both systems — the
# guard's first false positive, on its first otherwise-clean live run.
#
# An item's own marker always precedes prose about other items, so the FIRST hit over the combined
# vocabulary is the item's own status. Priority words must be in the same alternation: without them
# the scan skips straight past `MEDIUM` and finds the first stray `DONE` further along.
TERMINAL_WORDS = ("DONE", "CLOSED", "RETIRED", "MOOT", "SOLVED", "MERGED",
                  "WON'T DO", "MITIGATED", "DROPPED", "SUPERSEDED")
OPEN_WORDS     = ("HIGH", "MEDIUM", "LOW", "IN PROGRESS", "PAUSED", "DEFERRED")
STATUS = re.compile(r"\b(" + "|".join(re.escape(w) for w in TERMINAL_WORDS + OPEN_WORDS) + r")\b")

def is_done(line):
    m = STATUS.search(line)
    return bool(m) and m.group(1) in TERMINAL_WORDS

# THE FILE HAS TWO REGIONS AND BOTH CARRY REFERENCES.
#
#   1. An ordered priority list near the top — `1. **B46** — ... [Linear EMA-35].` — which CLAUDE.md
#      calls the ordered source of truth. Each item is self-contained: B-number, status and ref all
#      on ONE line.
#   2. The `### B<n>` detail sections below it, where the ref usually sits on a later line.
#
# The first cut scanned only region 2 and silently missed 7 live references — reporting 19 of 45 on
# its first real run. That is the same "supporting only one format halves coverage" failure this
# file's own header warns about, committed while writing the warning.
LIST_ITEM = re.compile(r'^\s*(?:\d+\.|[-*])\s+\*\*(B[\d.]+)\*\*')

rows, cur, done, seen = [], None, False, set()

def add(bnum, done_flag, line):   # param renamed: `is_done` shadowed the function above
    for ref in REF.findall(line):
        key = (bnum, ref)
        if key in seen:
            return
        seen.add(key)
        rows.append(f"{bnum}\t{ref}\t{'done' if done_flag else 'open'}")

for line in lines:
    li = LIST_ITEM.match(line)
    if li:
        # Self-contained: judge status from THIS line, and do not disturb the section cursor.
        add(li.group(1), is_done(line), line)
        continue

    h = re.match(r'^### (B[\d.]+)\b(.*)$', line)
    if h:
        if "(original" in line:
            cur = None                      # inside a collapsed duplicate: ignore its refs
            continue
        cur, done = h.group(1), is_done(line)
        # DO NOT `continue` HERE. The `[Linear EMA-46]` form appears INSIDE the heading itself
        # (`— **DONE 2026-08-18 [Linear EMA-46].**`), so skipping to the next line drops every
        # reference written that way — silently, and the dropped half looks like the passing half.
    if cur is None:
        continue
    add(cur, done, line)

if not rows:
    print(f"no `Linear: EMA-<n>` references found in {path}", file=sys.stderr)
    raise SystemExit(2)
print("\n".join(rows))
PY
}

# --- reading Linear ------------------------------------------------------------------------------
#
# linear_snapshot -> a JSON object keyed by issue identifier.
#
# The GraphQL query pulls EVERY issue on the team, not just the referenced ones: check B needs to see
# open issues the backlog never mentions, which is exactly how a project-less issue hides.
linear_snapshot() {
  if [ -n "${LINEAR_SNAPSHOT_JSON:-}" ]; then
    [ -r "$LINEAR_SNAPSHOT_JSON" ] || { echo "FATAL: cannot read $LINEAR_SNAPSHOT_JSON" >&2; return 1; }
    cat "$LINEAR_SNAPSHOT_JSON"
    return 0
  fi
  # The key may live in the gitignored scripts/.env alongside every other lab credential.
  #
  # THE PATH IS OVERRIDABLE so the no-key branch stays testable. Before a real key existed, the
  # "missing LINEAR_API_KEY is fatal" test passed for an ENVIRONMENTAL reason rather than a logical
  # one — the moment a key landed in scripts/.env the guard loaded it and the test went red. A test
  # that only passes while a file happens to be absent is not testing the code.
  if [ -z "${LINEAR_API_KEY:-}" ]; then
    local envf="${LINEAR_ENV_FILE:-$(dirname "${BASH_SOURCE[0]}")/.env}"
    # shellcheck disable=SC1090
    [ -r "$envf" ] && { set -a; . "$envf"; set +a; }
  fi
  if [ -z "${LINEAR_API_KEY:-}" ]; then
    echo "FATAL: LINEAR_API_KEY is not set (env or scripts/.env)." >&2
    echo "       Create one at Linear -> Settings -> Security & access -> New API key," >&2
    echo "       then add LINEAR_API_KEY=lin_api_... to the gitignored scripts/.env." >&2
    return 1
  fi
  local body http
  body="$(mktemp)"
  http="$(curl -s -o "$body" -w '%{http_code}' -X POST https://api.linear.app/graphql \
    -H "Authorization: ${LINEAR_API_KEY}" -H 'Content-Type: application/json' \
    -d "{\"query\":\"{ team(id: \\\"${LINEAR_TEAM}\\\") { issues(first: 250) { nodes { identifier state { type name } project { name } } } } }\"}")" || {
      echo "FATAL: could not reach the Linear API (curl transport failure)." >&2; rm -f "$body"; return 1; }
  # The status is read explicitly. `curl -sf | python3` collapses a 401 to empty input, and an empty
  # snapshot reads as "no issues" — a clean pass over nothing.
  if [ "$http" != "200" ]; then
    echo "FATAL: Linear API returned HTTP ${http}." >&2; rm -f "$body"; return 1
  fi
  python3 - "$body" <<'PY' || { rm -f "$body"; return 1; }
import json, sys
doc = json.load(open(sys.argv[1], encoding="utf-8"))
if "errors" in doc:
    print("FATAL: Linear GraphQL errors: " + json.dumps(doc["errors"])[:300], file=sys.stderr)
    raise SystemExit(1)
nodes = (((doc.get("data") or {}).get("team") or {}).get("issues") or {}).get("nodes")
if nodes is None:
    print("FATAL: unexpected Linear response shape", file=sys.stderr); raise SystemExit(1)
out = {}
for n in nodes:
    out[n["identifier"]] = {
        "stateType": (n.get("state") or {}).get("type"),
        "state":     (n.get("state") or {}).get("name"),
        "project":   (n.get("project") or {}).get("name") if n.get("project") else None,
    }
print(json.dumps(out))
PY
  rm -f "$body"
}

main() {
  local list_only=0
  [ "${1-}" = "--list" ] && list_only=1
  command -v python3 >/dev/null 2>&1 || { echo "python3 not found on PATH" >&2; exit 2; }

  local refs snap
  refs="$(backlog_refs "$BACKLOG_FILE")" || exit 2
  snap="$(linear_snapshot)"              || exit 2

  # BY FILE, NOT BY INTERPOLATION. The first cut pasted "$refs" straight into an unquoted heredoc,
  # which lets any `$` in the data reach the shell and mangles the script silently.
  #
  # WORKDIR IS GLOBAL, NOT `local`. An EXIT trap runs after main has returned, so a `local dir` is
  # already out of scope by then — and under `set -u` the trap itself dies with "dir: unbound
  # variable" AFTER the OK line has printed, turning a clean run into exit 1. Caught by the tests.
  WORKDIR="$(mktemp -d)"
  trap 'rm -rf "$WORKDIR"' EXIT
  local dir="$WORKDIR"
  printf '%s' "$snap"  > "$dir/snap.json"
  printf '%s\n' "$refs" > "$dir/refs.tsv"

  python3 - "$dir/snap.json" "$dir/refs.tsv" "$list_only" <<'PY'
import json, sys
snapfile, reffile, list_only = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
try:
    snap = json.load(open(snapfile, encoding="utf-8"))
except Exception as exc:
    print(f"FATAL: could not parse the Linear snapshot: {exc}", file=sys.stderr)
    raise SystemExit(2)
if not isinstance(snap, dict) or not snap:
    print("FATAL: the Linear snapshot is EMPTY - refusing to report OK over zero issues.", file=sys.stderr)
    raise SystemExit(2)

TERMINAL = {"completed", "canceled", "duplicate"}
refs = [l.split("\t") for l in open(reffile, encoding="utf-8").read().strip().split("\n") if l.strip()]

drift, missing, orphan = [], [], []
for bnum, ema, status in refs:
    row = snap.get(ema)
    if row is None:
        missing.append((bnum, ema)); continue
    st = row.get("stateType") or ""
    if list_only:
        print(f"  {bnum:8s} {ema:9s} backlog={status:5s} "
              f"linear={row.get('state') or '?':12s} project={row.get('project') or '(none)'}")
    if status == "done" and st not in TERMINAL:
        drift.append((bnum, ema, row.get("state")))

for ema, row in sorted(snap.items()):
    if (row.get("stateType") or "") in TERMINAL:
        continue
    if not row.get("project"):
        orphan.append((ema, row.get("state")))

if list_only:
    print(f"listed {len(refs)} backlog->Linear reference(s).")
    raise SystemExit(0)

if missing:
    for b, e in missing:
        print(f"  {b} references {e}, which the Linear team does not contain", file=sys.stderr)
    print(f"FATAL: {len(missing)} backlog reference(s) point at unknown issues.", file=sys.stderr)
    raise SystemExit(2)

fail = False
if drift:
    print("", file=sys.stderr)
    print("BACKLOG SAYS DONE, LINEAR SAYS OPEN:", file=sys.stderr)
    for b, e, s in drift:
        print(f"  {b:8s} {e:9s} is still '{s}' in Linear", file=sys.stderr)
    fail = True
if orphan:
    print("", file=sys.stderr)
    print("OPEN ISSUES WITH NO PROJECT (invisible to every filtered view):", file=sys.stderr)
    for e, s in orphan:
        print(f"  {e:9s} {s}", file=sys.stderr)
    print("  Assign each a project (Weyland Lab / rogueone Hardware / Stud.IO) — this team runs",
          file=sys.stderr)
    print("  two products, and project is the only thing separating them.", file=sys.stderr)
    fail = True

if fail:
    print("", file=sys.stderr)
    print("DoD Pillar 5 is the one pillar with no automatic check; this is that check.", file=sys.stderr)
    raise SystemExit(1)
print(f"OK - {len(refs)} backlog->Linear reference(s) reconciled, no project-less open issues.")
PY
}

if [ -z "${LINEAR_SYNC_LIB:-}" ]; then
  main "$@"
fi
