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
# documents make claims about each other, and this compares them.
#
# COVERAGE (widened 2026-09-10): reconciles EVERY backlog item — every `### B/U<n>` heading and every
# `**B/U<n>**` list entry — not just the ~45 that happen to carry an inline `Linear EMA-##` ref. The
# join key is the B/U-number in the Linear issue TITLE ("B160 — ..."); the inline ref is only a
# FALLBACK, used for the handful of weyland issues whose title carries no number (e.g. B156 -> EMA-213
# titled "Audit data mesh ..."). Number-primary matching also makes narrated SIBLING/SUPERSEDED refs
# (B66 names its EMA-56 sibling; B155 names the EMA-136 it supersedes) harmless — they are not the key.
#
# EIGHT CHECKS, all mechanically detectable. "WEYLAND SCOPE" (checks E/F) = the projects of the Linear
# initiative $LINEAR_SCOPE_INITIATIVE (default "Lab & Systems") — the projects whose work docs/backlog.md
# governs. It is read LIVE from Linear (B119 initiatives, 2026-09-24), replacing a hard-coded denylist of
# "other products" that silently treated every new project (Algopedia, freejack, ...) as weyland. Adding a
# project to that initiative is the ONE act that puts it in scope. No/empty scope initiative = exit 2.
#
#   A. STATUS drift — a backlog entry marked DONE that names a Linear issue NOT in a terminal state.
#      Deliberately ONE-WAY: an issue closed in Linear while the backlog entry is still open is a
#      normal mid-flight state, not drift.
#   B. PROJECT-less OPEN issue. This team runs multiple products (Weyland Lab, Stud.IO, ...) and project
#      is what separates them — an unassigned open issue is invisible to every filtered view. Found
#      EMA-186 and EMA-172 that way.
#   C. PRIORITY drift — a backlog HIGH/MEDIUM/LOW tag that disagrees with the Linear priority FIELD. The
#      backlog is the tier SoT (CLAUDE.md; see the `register()` note below — the ordered list's tier is
#      authoritative), so this flags where Linear's priority field has drifted from it. The class that
#      slipped past the status-only guard twice (B134, B87). Only for open items that declare a tier, and
#      only when Linear's priority maps to one (Urgent/None never flag).
#      NOTE (2026-09-22, B119): the redundant Linear High/Medium/Low *labels* were RETIRED — priority now
#      lives ONLY in the native `priority` field, which is exactly what this check reads (`n.get("priority")`
#      below). Do NOT add label-reading logic here. Rationale: docs/concepts/linear-evaluation.md.
#   D. MISSING from Linear — a backlog item with no Linear issue at all (untracked; the B128/B151 class).
#   E. ORPHAN in Linear — a weyland-numbered OPEN issue no backlog item covers (fell out of backlog.md),
#      only for projects in the weyland scope; the other initiatives' projects keep their own records.
#   F. UNNUMBERED weyland issue — a weyland-project issue (OPEN or DONE) whose title carries no weyland
#      number and which no backlog entry references. This is the class that hid EMA-172/191/208 for
#      weeks: checks D/E join on the number in the title, and E skips terminal issues, so an issue
#      created straight in Linear without a B-number is invisible to the whole number-based
#      reconciliation — the number is both the fix and the precondition for detection. Only for projects
#      in the weyland scope (others are not B-numbered), minus issues a backlog entry already cites by id.
#   G. REPO<->PROJECT parity — every ACTIVE repo in repos.yaml maps 1:1 to a live Linear Project (the
#      scaffold-all decision, 2026-09-23; docs/concepts/linear-evaluation.md). The map is the repo's
#      `linear_project:` NAME. G1 = an active repo with NO linear_project (a repo added to repos.yaml
#      but never given a project — the onboarding gap); G2 = a linear_project naming a project Linear
#      no longer has (rename/delete/typo). Read from a PROJECTS query, NOT the issue snapshot — an empty
#      project has zero issues and so never appears there, and the empty scaffolds are exactly the ones
#      repos map to. `stale` repos NEED no project, but ANY repo that declares a linear_project must have
#      it resolve (a stale/planned repo's mapping can't silently rot either).
#   H. PROJECT<->INITIATIVE — every live (non-canceled) project sits in EXACTLY one initiative. Initiatives
#      drive scope, so a project in NO initiative is in no one's scope (it could quietly hold weyland work)
#      and one in TWO is ambiguous. Runs with check G.
#
#   usage: scripts/check-linear-sync.sh [--list]
#          --list   print every item's verdict (status/project/tier/linpri + Linear-only orphans +
#                   repo->project map + weyland scope + project->initiative map), exit 0
#
# INPUTS. Live mode needs a Linear personal API key (Settings -> Security & access -> New API key):
#
#   LINEAR_API_KEY        read from the environment, or from the gitignored scripts/.env
#   LINEAR_TEAM           team key, default EMA
#
# For testing (and offline runs) point these at fixtures instead — they skip the API entirely:
#
#   LINEAR_SNAPSHOT_JSON  {"EMA-207": {"stateType": "...", "state": "...", "project": "..."|null}}
#   LINEAR_PROJECTS_JSON  ["Weyland Lab", "Algopedia", ...] — the live project NAMES for check G. When
#                         UNSET in snapshot mode, check G is not exercised (so the A-F fixtures need no
#                         projects/repos stub); live mode always queries projects and always runs G.
#   LINEAR_INITIATIVES_JSON {"Lab & Systems": ["Weyland Lab", ...], ...} — initiative -> project NAMES.
#                         REQUIRED in snapshot mode (the weyland scope for E/F comes from it; a snapshot run
#                         never falls back to the live API); live mode queries initiatives.
#   LINEAR_SCOPE_INITIATIVE which initiative is the weyland scope — default "Lab & Systems"
#   BACKLOG_FILE          defaults to docs/backlog.md
#   REPOS_FILE            defaults to repos.yaml — the active-repo <-> linear_project SoT for check G
#
# HOW IT RUNS: **blocking in CI** — `.woodpecker.yml` step `linear-sync` (its own step, because
# `repo-guards` is deliberately secret-free), secret `linear_api_key`, events cron+manual. Also run by
# hand at close-out. Unlike `check-secret-placeholders.sh` and `check-servicemonitor-coverage.sh` this
# one CAN live in CI: those need cluster read, this makes one outbound HTTPS call that NEEDS only read
# scope. (Least privilege: the CI secret should be a read-only key — the local scripts/.env key was found
# to be WRITE-capable on 2026-09-24, when it created the B119 custom views.) Verified green on pipeline 35.
#
# EXIT CODES are distinct on purpose. 1 = the estate has drift. 2 = the guard could not do its job.
# Conflating them means a missing token reads exactly like a clean backlog — and "checked nothing,
# found nothing" is the precise bug this whole family of guards exists to catch.
set -euo pipefail

BACKLOG_FILE="${BACKLOG_FILE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/docs/backlog.md}"
REPOS_FILE="${REPOS_FILE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/repos.yaml}"
LINEAR_TEAM="${LINEAR_TEAM:-EMA}"
LINEAR_SCOPE_INITIATIVE="${LINEAR_SCOPE_INITIATIVE:-Lab & Systems}"

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
# Item ids are B-numbers AND U-numbers: both carry Linear issues and both drift. Matching only `B`
# left a `Linear EMA-##` ref living in a `### U16` heading attributed to the PRECEDING `### B` section
# (its cursor never updated on the U-heading) — the 2026-09-09 B29<-U16/EMA-24 mis-map.
LIST_ITEM = re.compile(r'^\s*(?:\d+\.|[-*])\s+\*\*((?:B|U)[\d.]+)\*\*')
# Tier the item DECLARES (first HIGH/MEDIUM/LOW on its own line/heading), for the priority-drift check.
# Absent for items that state no tier (many do not — tier then lives only in Linear) and for done items.
TIER = re.compile(r'\b(HIGH|MEDIUM|LOW)\b')

def tier_of(line):
    m = TIER.search(line)
    return m.group(1) if m else ""

rows, cur, done, tier, seen = [], None, False, "", set()
items, reffed = {}, set()   # every item number seen (first-seen status/tier wins) · numbers that emitted a ref

def register(num, done_flag, tier_val):
    # First occurrence wins: the top ordered list (region 1) precedes the ### detail sections, and
    # CLAUDE.md calls the ordered list the source of truth — so the list's status/tier is authoritative.
    items.setdefault(num, ('done' if done_flag else 'open', tier_val))

def add(num, done_flag, tier_val, line):   # param renamed: `is_done` shadowed the function above
    for ref in REF.findall(line):
        key = (num, ref)
        if key in seen:
            return
        seen.add(key)
        reffed.add(num)
        rows.append(f"{num}\t{ref}\t{'done' if done_flag else 'open'}\t{tier_val}")

for line in lines:
    li = LIST_ITEM.match(line)
    if li:
        # Self-contained: judge status + tier from THIS line, and do not disturb the section cursor.
        register(li.group(1), is_done(line), tier_of(line))
        add(li.group(1), is_done(line), tier_of(line), line)
        continue

    h = re.match(r'^### ((?:B|U)[\d.]+)\b(.*)$', line)
    if h:
        if "(original" in line:
            cur = None                      # inside a collapsed duplicate: ignore its refs
            continue
        cur, done, tier = h.group(1), is_done(line), tier_of(line)
        register(cur, done, tier)
        # DO NOT `continue` HERE. The `[Linear EMA-46]` form appears INSIDE the heading itself
        # (`— **DONE 2026-08-18 [Linear EMA-46].**`), so skipping to the next line drops every
        # reference written that way — silently, and the dropped half looks like the passing half.
    if cur is None:
        continue
    add(cur, done, tier, line)

# Emit a ref-LESS row for every item that never produced a `Linear: EMA-##` ref, so FULL COVERAGE
# reconciliation (match-by-B-number against the Linear title) sees it too — this is how an item with
# no Linear issue at all (the B128/B151 class) becomes visible instead of silently unchecked.
for num, (st, tv) in items.items():
    if num not in reffed:
        rows.append(f"{num}\t-\t{st}\t{tv}")

# Fail closed on a backlog with NO ITEMS at all (empty/garbage) — but items-without-refs is now a
# checkable state (number-matched), not "checking nothing".
if not items:
    print(f"no backlog items (### B/U headings or **B/U** list entries) found in {path}", file=sys.stderr)
    raise SystemExit(2)
print("\n".join(rows))
PY
}

# --- parsing repos.yaml (check G) ----------------------------------------------------------------
#
# repos_projects <repos-file> -> `<repo>\t<linear_project|->` per ACTIVE repo.
#
# The scaffold-all decision (2026-09-23): every ACTIVE repo maps 1:1 to a Linear Project, recorded as
# the `linear_project:` NAME. `stale` repos are excluded (no project until reactivated). Uses pyyaml
# (as check-repo-coverage.sh does — the CI `linear-sync` step apk-adds `py3-yaml`). FAILS CLOSED: an
# unreadable/unparseable file, or zero active repos, is a broken guard, never an empty pass.
repos_projects() { # repos_projects <repos-file>
  local f="${1:?usage: repos_projects <repos-file>}"
  [ -r "$f" ] || { echo "FATAL: cannot read repos file: $f" >&2; return 1; }
  python3 - "$f" <<'PY' || return 1
import sys
try:
    import yaml
except ImportError as e:
    print(f"FATAL: pyyaml unavailable ({e}) — the linear-sync step must apk-add py3-yaml", file=sys.stderr)
    raise SystemExit(1)
try:
    d = yaml.safe_load(open(sys.argv[1], encoding="utf-8")) or {}
except Exception as exc:
    print(f"FATAL: could not parse repos.yaml: {exc}", file=sys.stderr); raise SystemExit(1)
repos = [r for r in (d.get("repos") or []) if isinstance(r, dict)]
active = [r for r in repos if r.get("status") == "active"]
if not active:
    print("FATAL: no active repos found in repos.yaml", file=sys.stderr); raise SystemExit(1)
# `<repo>\t<linear_project|->\t<required 1|0>`: an ACTIVE repo MUST map (required=1); a non-active repo
# that DECLARES a linear_project is emitted too (required=0) so its mapping is still validated.
for r in repos:
    lp = r.get("linear_project") or "-"
    if r.get("status") == "active":
        print(f"{r.get('name','?')}\t{lp}\t1")
    elif lp != "-":
        print(f"{r.get('name','?')}\t{lp}\t0")
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
  # Bounded so a hung API FAILS FAST instead of pinning the CI step for minutes. Still fails closed.
  http="$(curl -s --connect-timeout 10 --max-time 30 -o "$body" -w '%{http_code}' -X POST https://api.linear.app/graphql \
    -H "Authorization: ${LINEAR_API_KEY}" -H 'Content-Type: application/json' \
    -d "{\"query\":\"{ team(id: \\\"${LINEAR_TEAM}\\\") { issues(first: 250) { nodes { identifier title priority state { type name } project { name } } } } }\"}")" || {
      echo "FATAL: could not reach the Linear API (curl transport failure/timeout)." >&2; rm -f "$body"; return 1; }
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
        "priority":  n.get("priority"),   # Linear int: 0 None · 1 Urgent · 2 High · 3 Medium · 4 Low
        "title":     n.get("title"),      # to derive the B/U/SEC item-number for full-coverage matching
    }
print(json.dumps(out))
PY
  rm -f "$body"
}

# --- reading Linear projects (check G) -----------------------------------------------------------
#
# linear_projects -> a JSON array of live project NAMES.
#
# A SEPARATE query from linear_snapshot on purpose: an EMPTY project (0 issues) never appears in the
# issue snapshot's `project { name }`, so repo↔project parity cannot be derived from issues — the
# scaffolded-but-empty projects are exactly the ones a repo maps to. The fixture path skips the API.
linear_projects() {
  if [ -n "${LINEAR_PROJECTS_JSON:-}" ]; then
    [ -r "$LINEAR_PROJECTS_JSON" ] || { echo "FATAL: cannot read $LINEAR_PROJECTS_JSON" >&2; return 1; }
    cat "$LINEAR_PROJECTS_JSON"
    return 0
  fi
  # Load the key HERE, not relying on linear_snapshot having done it: both functions run under command
  # substitution (`projs="$(linear_projects)"`), so an `export` inside linear_snapshot's subshell never
  # reaches this one. This mirrors linear_snapshot's own load block (kept in step deliberately).
  if [ -z "${LINEAR_API_KEY:-}" ]; then
    local envf="${LINEAR_ENV_FILE:-$(dirname "${BASH_SOURCE[0]}")/.env}"
    # shellcheck disable=SC1090
    [ -r "$envf" ] && { set -a; . "$envf"; set +a; }
  fi
  if [ -z "${LINEAR_API_KEY:-}" ]; then
    echo "FATAL: LINEAR_API_KEY is not set for the projects query (env or scripts/.env)." >&2; return 1
  fi
  local body http
  body="$(mktemp)"
  http="$(curl -s --connect-timeout 10 --max-time 30 -o "$body" -w '%{http_code}' -X POST https://api.linear.app/graphql \
    -H "Authorization: ${LINEAR_API_KEY}" -H 'Content-Type: application/json' \
    -d "{\"query\":\"{ team(id: \\\"${LINEAR_TEAM}\\\") { projects(first: 250, filter: { status: { type: { nin: [\\\"canceled\\\"] } } }) { nodes { name } } } }\"}")" || {
      echo "FATAL: could not reach the Linear API for projects (curl transport failure/timeout)." >&2; rm -f "$body"; return 1; }
  if [ "$http" != "200" ]; then
    echo "FATAL: Linear API (projects) returned HTTP ${http}." >&2; rm -f "$body"; return 1
  fi
  python3 - "$body" <<'PY' || { rm -f "$body"; return 1; }
import json, sys
doc = json.load(open(sys.argv[1], encoding="utf-8"))
if "errors" in doc:
    print("FATAL: Linear GraphQL errors (projects): " + json.dumps(doc["errors"])[:300], file=sys.stderr)
    raise SystemExit(1)
nodes = (((doc.get("data") or {}).get("team") or {}).get("projects") or {}).get("nodes")
if nodes is None:
    print("FATAL: unexpected Linear projects response shape", file=sys.stderr); raise SystemExit(1)
print(json.dumps([n.get("name") for n in nodes if n.get("name")]))
PY
  rm -f "$body"
}

# --- reading Linear initiatives (weyland scope + check H) ----------------------------------------
#
# linear_initiatives -> a JSON object {initiative-name: [project names]}.
#
# The weyland scope for E/F is one initiative's membership, so this is REQUIRED on every run. In snapshot
# mode it must come from LINEAR_INITIATIVES_JSON — a fixture run never falls back to the live API (that
# would make tests depend on the network and on whatever key sits in scripts/.env).
linear_initiatives() {
  if [ -n "${LINEAR_INITIATIVES_JSON:-}" ]; then
    [ -r "$LINEAR_INITIATIVES_JSON" ] || { echo "FATAL: cannot read $LINEAR_INITIATIVES_JSON" >&2; return 1; }
    cat "$LINEAR_INITIATIVES_JSON"
    return 0
  fi
  if [ -n "${LINEAR_SNAPSHOT_JSON:-}" ]; then
    echo "FATAL: snapshot mode needs LINEAR_INITIATIVES_JSON — the weyland scope ('${LINEAR_SCOPE_INITIATIVE}') comes from it." >&2
    return 1
  fi
  if [ -z "${LINEAR_API_KEY:-}" ]; then
    local envf="${LINEAR_ENV_FILE:-$(dirname "${BASH_SOURCE[0]}")/.env}"
    # shellcheck disable=SC1090
    [ -r "$envf" ] && { set -a; . "$envf"; set +a; }
  fi
  if [ -z "${LINEAR_API_KEY:-}" ]; then
    echo "FATAL: LINEAR_API_KEY is not set for the initiatives query (env or scripts/.env)." >&2; return 1
  fi
  local body http
  body="$(mktemp)"
  http="$(curl -s --connect-timeout 10 --max-time 30 -o "$body" -w '%{http_code}' -X POST https://api.linear.app/graphql \
    -H "Authorization: ${LINEAR_API_KEY}" -H 'Content-Type: application/json' \
    -d '{"query":"{ initiatives(first: 50) { pageInfo { hasNextPage } nodes { name projects(first: 50) { pageInfo { hasNextPage } nodes { name } } } } }"}')" || {
      echo "FATAL: could not reach the Linear API for initiatives (curl transport failure/timeout)." >&2; rm -f "$body"; return 1; }
  if [ "$http" != "200" ]; then
    echo "FATAL: Linear API (initiatives) returned HTTP ${http}." >&2; rm -f "$body"; return 1
  fi
  python3 - "$body" <<'PY' || { rm -f "$body"; return 1; }
import json, sys
doc = json.load(open(sys.argv[1], encoding="utf-8"))
if "errors" in doc:
    print("FATAL: Linear GraphQL errors (initiatives): " + json.dumps(doc["errors"])[:300], file=sys.stderr)
    raise SystemExit(1)
conn = (doc.get("data") or {}).get("initiatives") or {}
nodes = conn.get("nodes")
if nodes is None:
    print("FATAL: unexpected Linear initiatives response shape", file=sys.stderr); raise SystemExit(1)
# 50x50 keeps under Linear's 10000 query-complexity cap (100x100 was rejected at 11110). A truncated page
# would silently drop members, so any hasNextPage is fatal — widen the query, never trust a partial map.
if (conn.get("pageInfo") or {}).get("hasNextPage") or any(
        ((n.get("projects") or {}).get("pageInfo") or {}).get("hasNextPage") for n in nodes):
    print("FATAL: Linear initiatives response is paginated (>50) - a partial membership map would "
          "mis-scope the checks; add pagination.", file=sys.stderr); raise SystemExit(1)
print(json.dumps({n["name"]: [p["name"] for p in (n.get("projects") or {}).get("nodes", [])] for n in nodes}))
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
  local inits
  inits="$(linear_initiatives)"          || exit 2

  # CHECK G — repos.yaml active-repo <-> Linear project parity. Runs LIVE (no issue snapshot) or when a
  # projects fixture is explicitly provided. A pure A-F snapshot test (LINEAR_SNAPSHOT_JSON set, no
  # LINEAR_PROJECTS_JSON) does NOT exercise G — that is what keeps those tests from each needing a
  # projects+repos stub. Both inputs fail closed (exit 2) rather than skip silently.
  local check_g=0 projs="[]" repos_tsv=""
  if [ -z "${LINEAR_SNAPSHOT_JSON:-}" ] || [ -n "${LINEAR_PROJECTS_JSON:-}" ]; then
    check_g=1
    projs="$(linear_projects)"          || exit 2
    repos_tsv="$(repos_projects "$REPOS_FILE")" || exit 2
  fi

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
  printf '%s' "$projs" > "$dir/projs.json"
  printf '%s\n' "$repos_tsv" > "$dir/repos.tsv"
  printf '%s' "$inits" > "$dir/inits.json"

  python3 - "$dir/snap.json" "$dir/refs.tsv" "$list_only" "$dir/projs.json" "$dir/repos.tsv" "$check_g" \
    "$dir/inits.json" "$LINEAR_SCOPE_INITIATIVE" <<'PY'
import json, sys
snapfile, reffile, list_only = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
projsfile, reposfile, check_g = sys.argv[4], sys.argv[5], sys.argv[6] == "1"
initsfile, SCOPE_INITIATIVE = sys.argv[7], sys.argv[8]
try:
    snap = json.load(open(snapfile, encoding="utf-8"))
except Exception as exc:
    print(f"FATAL: could not parse the Linear snapshot: {exc}", file=sys.stderr)
    raise SystemExit(2)
if not isinstance(snap, dict) or not snap:
    print("FATAL: the Linear snapshot is EMPTY - refusing to report OK over zero issues.", file=sys.stderr)
    raise SystemExit(2)

# WEYLAND SCOPE = the projects of the scope initiative (Lab & Systems), read live. This replaced a
# hard-coded "other products" denylist that went stale the moment a new product project appeared
# (Algopedia's unnumbered issues were flagged as weyland work). Fail closed: a missing or empty scope
# initiative would make E/F check NOTHING and report OK, so it is exit 2, never "nothing in scope".
try:
    inits = json.load(open(initsfile, encoding="utf-8"))
except Exception as exc:
    print(f"FATAL: could not parse the Linear initiatives list: {exc}", file=sys.stderr)
    raise SystemExit(2)
if not isinstance(inits, dict) or SCOPE_INITIATIVE not in inits:
    print(f"FATAL: initiative '{SCOPE_INITIATIVE}' not found in Linear - it defines the weyland scope "
          f"(which projects this backlog governs); refusing to reconcile over an unknown scope.", file=sys.stderr)
    raise SystemExit(2)
scope = set(inits.get(SCOPE_INITIATIVE) or [])
if not scope:
    print(f"FATAL: initiative '{SCOPE_INITIATIVE}' has NO projects - an empty scope would check nothing "
          f"and report OK.", file=sys.stderr)
    raise SystemExit(2)

# CHECK G — repos.yaml active-repo <-> Linear project parity (the scaffold-all decision, 2026-09-23).
# G1: an active repo with no linear_project (SoT/onboarding gap). G2: a linear_project naming a project
# Linear no longer has (rename/delete/typo). Fail closed: zero live projects, or no active repos, is a
# broken guard (exit 2), never a pass over nothing. Parsed here (before the reconciliation loops) so an
# exit-2 condition is never masked by an exit-1 finding.
repo_noproj, repo_missing = [], []
h_none, h_multi = [], []
if check_g:
    try:
        live_projects = set(json.load(open(projsfile, encoding="utf-8")))
    except Exception as exc:
        print(f"FATAL: could not parse the Linear projects list: {exc}", file=sys.stderr)
        raise SystemExit(2)
    if not live_projects:
        print("FATAL: no Linear projects returned - refusing to verify repo<->project parity over zero "
              "projects (token/API failure looks exactly like 'all mapped').", file=sys.stderr)
        raise SystemExit(2)
    repo_rows = [l.split("\t") for l in open(reposfile, encoding="utf-8").read().strip().split("\n") if l.strip()]
    if not repo_rows:
        print("FATAL: no active repos parsed from repos.yaml for check G.", file=sys.stderr)
        raise SystemExit(2)
    # Rows are <repo>\t<linear_project|->\t<required>. G1 applies only to ACTIVE repos (required=1);
    # G2 applies to ANY repo that declares a project, so a stale repo's name can't rot unnoticed.
    for parts in repo_rows:
        repo = parts[0]
        lp = parts[1] if len(parts) > 1 else "-"
        required = (parts[2] if len(parts) > 2 else "1") == "1"
        if not lp or lp == "-":
            if required:
                repo_noproj.append(repo)
        elif lp not in live_projects:
            repo_missing.append((repo, lp))
    # CHECK H — every live project sits in EXACTLY one initiative. Initiatives drive scope, so a project
    # in none is in no one's scope (weyland work could hide there unchecked) and one in two is ambiguous.
    # Only LIVE projects count: an initiative may still list a completed/canceled project.
    member_of = {}
    for ini, projects in inits.items():
        for p in projects or []:
            member_of.setdefault(p, []).append(ini)
    for p in sorted(live_projects):
        where = member_of.get(p, [])
        if not where:
            h_none.append(p)
        elif len(where) > 1:
            h_multi.append((p, sorted(where)))

import re as _re
TERMINAL = {"completed", "canceled", "duplicate"}
# Linear priority int -> the backlog's tier vocabulary. 0 (None) / 1 (Urgent) are not backlog tiers,
# so an item at those priorities is not tier-compared (no false drift against an unmapped priority).
PRIORITY_TIER = {2: "HIGH", 3: "MEDIUM", 4: "LOW"}
# The item-number carried at the START of a Linear issue title — the full-coverage join key, so items
# WITHOUT an inline `Linear EMA-##` ref (the majority) still get reconciled by number, not skipped.
NUM = _re.compile(r'^\s*((?:B|U)[\d.]+|SEC-\d+|B-RT)\b')
def num_of(title):
    m = NUM.match(title or "")
    return m.group(1) if m else None

rawrefs = [l.split("\t") for l in open(reffile, encoding="utf-8").read().strip().split("\n") if l.strip()]

# Index every Linear issue by the number in its title (first wins; genuine dupes surface via orphan).
lin_by_num = {}
for e, r in snap.items():
    n = num_of(r.get("title"))
    if n and n not in lin_by_num:
        lin_by_num[n] = e

# Collapse the per-ref rows to ONE record per backlog item: its status, tier, and the set of inline
# refs it names (an entry legitimately narrates SIBLING/SUPERSEDED issues' refs, e.g. B66 mentions its
# EMA-56 sibling, B155 mentions the EMA-136 it supersedes — so a single ref is a hint, never the key).
by_num = {}
for parts in rawrefs:
    bnum, ema_ref, status = parts[0], parts[1], parts[2]
    tier = parts[3] if len(parts) > 3 else ""
    rec = by_num.setdefault(bnum, {"status": status, "tier": tier, "refs": []})
    if ema_ref != "-" and ema_ref not in rec["refs"]:
        rec["refs"].append(ema_ref)

backlog_nums = set(by_num)
# Every EMA-id any backlog entry cites inline — the set that makes the fallback join (B156 -> EMA-213,
# a weyland issue whose Linear title carries no number) legitimate, so the unnumbered check below does
# not flag an issue the backlog already references by id.
referenced = {r for rec in by_num.values() for r in rec["refs"]}
drift, missing, orphan, tierdrift, nolinear, orphan_num, unnumbered = [], [], [], [], [], [], []
for bnum, rec in by_num.items():
    status, tier, brefs = rec["status"], rec["tier"], rec["refs"]
    # PRIMARY join = the B/U number in the Linear title (immune to narrated sibling refs). FALLBACK =
    # an inline ref, for the handful of weyland issues whose Linear title carries no number (e.g. B156
    # -> EMA-213 titled "Audit data mesh ..."); prefer a fallback ref that actually exists in Linear.
    ema = lin_by_num.get(bnum)
    if ema is None:
        ema = next((r for r in brefs if r in snap), brefs[0] if brefs else None)
    if ema is None:
        nolinear.append((bnum, status, tier))
        if list_only:
            print(f"  {bnum:8s} {'(none)':9s} backlog={status:5s} "
                  f"linear={'(no issue)':12s} project={'-':14s} tier={tier or '-':7s} linpri=-")
        continue
    row = snap.get(ema)
    if row is None:
        missing.append((bnum, ema)); continue   # an inline ref pointing at a nonexistent issue — fatal
    st = row.get("stateType") or ""
    lin_tier = PRIORITY_TIER.get(row.get("priority"))
    if list_only:
        print(f"  {bnum:8s} {ema:9s} backlog={status:5s} "
              f"linear={row.get('state') or '?':12s} project={row.get('project') or '(none)':14s} "
              f"tier={tier or '-':7s} linpri={lin_tier or '-'}")
    if status == "done" and st not in TERMINAL:
        drift.append((bnum, ema, row.get("state")))
    # PRIORITY DRIFT — the class that slipped past this guard twice (B134, B87): it checked status,
    # never priority. Only for OPEN items that DECLARE a tier, and only when Linear's priority maps to
    # a backlog tier — so an item with no stated tier, or at Urgent/None, is never falsely flagged.
    if status != "done" and tier and lin_tier and lin_tier != tier and st not in TERMINAL:
        tierdrift.append((bnum, ema, tier, lin_tier))

for ema, row in sorted(snap.items()):
    stt = row.get("stateType") or ""
    proj = row.get("project")
    n = num_of(row.get("title"))
    # UNNUMBERED WEYLAND ISSUE — the EMA-172/191/208 blind spot. A weyland-project issue whose title
    # carries no weyland number and which no backlog entry references never got a B-number, so
    # number-based reconciliation cannot see it — the number is both the fix and the precondition for
    # detection. Checked for OPEN AND DONE (two of the three that hid here were Done), so it runs
    # BEFORE the terminal skip below. A project-less issue is the `orphan` (project) finding instead,
    # so this requires a project; only weyland-scope projects count (other products keep their own backlog).
    if proj and proj in scope and n is None and ema not in referenced:
        unnumbered.append((ema, row.get("state"), proj))
    if stt in TERMINAL:
        continue
    if not proj:
        orphan.append((ema, row.get("state")))
    # ORPHAN IN LINEAR — a weyland-numbered OPEN issue that no backlog item covers (fell out of the
    # backlog). Only weyland-scope projects count; other products keep their own backlogs.
    if n and n not in backlog_nums and proj in scope:
        orphan_num.append((ema, n, row.get("state")))

if list_only:
    if orphan_num:
        print("  --- Linear issues with a weyland number but NO backlog item ---")
        for e, n, s in orphan_num:
            print(f"  {n:8s} {e:9s} {s} (in Linear, absent from backlog.md)")
    if unnumbered:
        print("  --- Weyland issues with NO number in their title and NO backlog item ---")
        for e, s, p in unnumbered:
            print(f"  {'(no #)':8s} {e:9s} {s} in {p} (no B-number, unreferenced by backlog.md)")
    print(f"  --- weyland scope = initiative '{SCOPE_INITIATIVE}': {', '.join(sorted(scope))} ---")
    if check_g:
        print("  --- repos.yaml repo -> Linear project (check G) ---")
        for parts in repo_rows:
            repo = parts[0]; lp = parts[1] if len(parts) > 1 else "-"
            required = (parts[2] if len(parts) > 2 else "1") == "1"
            if not lp or lp == "-":
                verdict = "NO PROJECT FIELD" if required else "none (not active)"
            else:
                verdict = "OK" if lp in live_projects else "MISSING IN LINEAR"
            print(f"  {repo:42s} -> {lp:34s} [{verdict}]")
        print("  --- live Linear project -> initiative (check H) ---")
        for p in sorted(live_projects):
            where = member_of.get(p, [])
            print(f"  {p:42s} -> {' + '.join(sorted(where)) or '(NO INITIATIVE)'}")
    print(f"listed {len(backlog_nums)} backlog item(s); "
          f"{len(nolinear)} with no Linear issue, {len(orphan_num)} Linear-only, "
          f"{len(unnumbered)} unnumbered-and-unreferenced.")
    raise SystemExit(0)

if missing:
    for b, e in missing:
        print(f"  {b} references {e}, which the Linear team does not contain", file=sys.stderr)
    print(f"FATAL: {len(missing)} backlog reference(s) point at unknown issues.", file=sys.stderr)
    raise SystemExit(2)

fail = False
if nolinear:
    print("", file=sys.stderr)
    print("BACKLOG ITEMS WITH NO LINEAR ISSUE (untracked — invisible to every Linear view):", file=sys.stderr)
    for b, s, t in nolinear:
        print(f"  {b:8s} backlog={s} tier={t or '-'} — create a Linear issue titled '{b} — ...'", file=sys.stderr)
    fail = True
if orphan_num:
    print("", file=sys.stderr)
    print("LINEAR ISSUES WITH A WEYLAND NUMBER BUT NO BACKLOG ITEM (fell out of backlog.md):", file=sys.stderr)
    for e, n, s in orphan_num:
        print(f"  {n:8s} {e:9s} '{s}' — restore it to backlog.md, or close it if truly dropped", file=sys.stderr)
    fail = True
if unnumbered:
    print("", file=sys.stderr)
    print("WEYLAND ISSUES WITH NO NUMBER IN THEIR TITLE AND NO BACKLOG ITEM (unreconcilable):", file=sys.stderr)
    for e, s, p in unnumbered:
        print(f"  {e:9s} '{s}' in {p} — give it a B-number (title 'B<n> — ...') + a backlog entry, "
              f"or reference it from one", file=sys.stderr)
    print("  This is the class that hid EMA-172/191/208: a weyland issue created in Linear with no",
          file=sys.stderr)
    print("  B-number is invisible to number-based reconciliation — the number is the join key.",
          file=sys.stderr)
    fail = True
if drift:
    print("", file=sys.stderr)
    print("BACKLOG SAYS DONE, LINEAR SAYS OPEN:", file=sys.stderr)
    for b, e, s in drift:
        print(f"  {b:8s} {e:9s} is still '{s}' in Linear", file=sys.stderr)
    fail = True
if tierdrift:
    print("", file=sys.stderr)
    print("PRIORITY DRIFT — backlog tier != Linear priority (Linear is the tier source of truth):", file=sys.stderr)
    for b, e, bt, lt in tierdrift:
        print(f"  {b:8s} {e:9s} backlog={bt}  linear={lt}", file=sys.stderr)
    print("  Align both (backlog HIGH/MEDIUM/LOW tag + Linear priority) — a rebalance must move each.", file=sys.stderr)
    fail = True
if orphan:
    print("", file=sys.stderr)
    print("OPEN ISSUES WITH NO PROJECT (invisible to every filtered view):", file=sys.stderr)
    for e, s in orphan:
        print(f"  {e:9s} {s}", file=sys.stderr)
    print("  Assign each a project — this team runs several products, and project is the only thing",
          file=sys.stderr)
    print("  separating them (and the only thing an initiative can scope).", file=sys.stderr)
    fail = True
if repo_noproj:
    print("", file=sys.stderr)
    print("ACTIVE REPOS WITH NO linear_project IN repos.yaml (every active repo maps 1:1 to a project):",
          file=sys.stderr)
    for r in repo_noproj:
        print(f"  {r:42s} — create a Linear project for it and add `linear_project: \"<name>\"` "
              f"(run scripts/onboard-repo.sh)", file=sys.stderr)
    fail = True
if repo_missing:
    print("", file=sys.stderr)
    print("repos.yaml linear_project NAMES A PROJECT LINEAR DOES NOT HAVE (renamed, deleted, or a typo):",
          file=sys.stderr)
    for r, lp in repo_missing:
        print(f"  {r:42s} -> '{lp}' — create/rename the project, or fix the SoT name", file=sys.stderr)
    fail = True
if h_none:
    print("", file=sys.stderr)
    print("LIVE PROJECTS IN NO INITIATIVE (initiatives drive scope — an unfiled project is in no one's scope):",
          file=sys.stderr)
    for p in h_none:
        print(f"  {p:42s} — add it to exactly one initiative (Lab & Systems if docs/backlog.md governs it)",
              file=sys.stderr)
    fail = True
if h_multi:
    print("", file=sys.stderr)
    print("PROJECTS IN MORE THAN ONE INITIATIVE (scope is ambiguous — keep exactly one):", file=sys.stderr)
    for p, where in h_multi:
        print(f"  {p:42s} in {' + '.join(where)}", file=sys.stderr)
    fail = True

if fail:
    print("", file=sys.stderr)
    print("DoD Pillar 5 is the one pillar with no automatic check; this is that check.", file=sys.stderr)
    raise SystemExit(1)
print(f"OK - {len(backlog_nums)} backlog item(s) reconciled with Linear (status + priority + coverage), "
      f"no project-less open issues, no orphans"
      + f", weyland scope = '{SCOPE_INITIATIVE}' ({len(scope)} project(s))"
      + (f"; {sum(1 for r in repo_rows if (r[2] if len(r) > 2 else '1') == '1')} active repo(s) mapped 1:1 "
         f"to live projects; {len(live_projects)} live project(s) each in exactly one initiative."
         if check_g else "."))
PY
}

if [ -z "${LINEAR_SYNC_LIB:-}" ]; then
  main "$@"
fi
