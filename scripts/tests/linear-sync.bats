#!/usr/bin/env bats
# DoD Pillar 5 — backlog/Linear status reconciliation.
#
# WHY THIS EXISTS: Pillar 5 was the ONE pillar with nothing that could contradict the person filling
# it in. Every other pillar has a checker — check-mermaid.sh, check-cron-freshness-budgets.sh, the
# bats suite, eyes on a dashboard. Pillar 5 was prose in a checklist, so writing the tick WAS the
# work. On 2026-08-26 the B148 DoD recorded "5 OK — Linear EMA-207" while no Linear call had been
# made at all; the issue sat in Backlog. B143 had been sitting open for two days after shipping.
#
# Both drifts are mechanically detectable, and this is what detects them:
#
#   A. A backlog entry marked DONE that names a Linear issue which is NOT in a terminal state.
#   B. An OPEN Linear issue with no project — invisible to every filtered view while still counting
#      in the team total. Found two High-priority weyland issues that way (EMA-186, EMA-172), one
#      of them open since 2026-08-12 and absent from every "what's next" answer.
#
# FAILS CLOSED. No token, an unparseable snapshot, or zero refs parsed are all loud errors — a guard
# that checks nothing must never report success. That is the defect this whole family exists to catch.

setup() {
  load helper
  setup_stubs
  GUARD="$REPO_ROOT/scripts/check-linear-sync.sh"
}

teardown() {
  teardown_stubs
}

lib_source() {
  LINEAR_SYNC_LIB=1 source "$GUARD"
}

@test "the guard exists" {
  [ -f "$GUARD" ]
}

# --- terminal-state decision ---------------------------------------------------------------------

@test "is_terminal: completed, canceled and duplicate are terminal" {
  lib_source
  for s in completed canceled duplicate; do
    run is_terminal "$s"
    [ "$status" -eq 0 ]
  done
}

@test "is_terminal: backlog, unstarted and started are NOT terminal" {
  # `started` covers both "In Progress" and "In Review" in this workspace.
  lib_source
  for s in backlog unstarted started; do
    run is_terminal "$s"
    [ "$status" -ne 0 ]
  done
}

@test "is_terminal: an UNKNOWN state type is NOT terminal — fails closed" {
  # A new Linear state nobody taught this function about must not silently count as done.
  lib_source
  run is_terminal "banana"
  [ "$status" -ne 0 ]
  run is_terminal ""
  [ "$status" -ne 0 ]
}

# --- parsing the backlog -------------------------------------------------------------------------

@test "backlog_refs finds BOTH reference formats" {
  # The file uses `Linear: EMA-207` and `[Linear EMA-46]`. Supporting only one silently halves
  # coverage, and the half that goes unchecked looks identical to the half that passes.
  lib_source
  cat > "$STUB_DIR/b.md" <<'MD'
### B148 — something — **DONE (2026-08-26)**
Linear: EMA-207. Relates B147.

### B57 — **Build farm** — **DONE 2026-08-18 [Linear EMA-46].** deferred bits
MD
  run backlog_refs "$STUB_DIR/b.md"
  [ "$status" -eq 0 ]
  [[ "$output" == *"EMA-207"* ]]
  [[ "$output" == *"EMA-46"* ]]
}

@test "backlog_refs marks an entry done vs open" {
  lib_source
  cat > "$STUB_DIR/b.md" <<'MD'
### B148 — closed thing — **DONE (2026-08-26)**
Linear: EMA-207.

### B134 — open thing — **HIGH (2026-08-20)**
Linear: EMA-195.
MD
  run backlog_refs "$STUB_DIR/b.md"
  [[ "$output" == *"EMA-207"*"done"* ]]
  [[ "$output" == *"EMA-195"*"open"* ]]
}

@test "backlog_refs ignores a collapsed (original entry) duplicate" {
  # Closed items keep their superseded text inside <details> under a `(original entry)` heading.
  # Counting it would double every closed item and could resurrect a stale status.
  lib_source
  cat > "$STUB_DIR/b.md" <<'MD'
### B148 — thing — **DONE (2026-08-26)**
Linear: EMA-207.
<details><summary>Original entry</summary>

### B148 (original entry) — **MEDIUM (2026-08-25)**
Linear: EMA-207.
</details>
MD
  run backlog_refs "$STUB_DIR/b.md"
  [ "$(printf '%s' "$output" | grep -c 'EMA-207')" -eq 1 ]
}

@test "backlog_refs on a file with NO refs is FATAL, not an empty pass" {
  lib_source
  printf '# nothing here\n' > "$STUB_DIR/empty.md"
  run backlog_refs "$STUB_DIR/empty.md"
  [ "$status" -ne 0 ]
}

@test "backlog_refs on a missing file is FATAL" {
  lib_source
  run backlog_refs "$STUB_DIR/nope.md"
  [ "$status" -ne 0 ]
}

# --- check A: backlog DONE vs Linear open --------------------------------------------------------

@test "A: backlog DONE + Linear terminal passes" {
  cat > "$STUB_DIR/b.md" <<'MD'
### B148 — thing — **DONE (2026-08-26)**
Linear: EMA-207.
MD
  printf '{"EMA-207":{"stateType":"completed","state":"Done","project":"Weyland Lab"}}' > "$STUB_DIR/s.json"
  BACKLOG_FILE="$STUB_DIR/b.md" LINEAR_SNAPSHOT_JSON="$STUB_DIR/s.json" run bash "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"OK"* ]]
}

@test "A: backlog DONE + Linear still Backlog FAILS and names both ids — the B143 drift" {
  cat > "$STUB_DIR/b.md" <<'MD'
### B143 — woodpecker upgrade — **DONE (2026-08-24)**
Linear: EMA-199.
MD
  printf '{"EMA-199":{"stateType":"backlog","state":"Backlog","project":"Weyland Lab"}}' > "$STUB_DIR/s.json"
  BACKLOG_FILE="$STUB_DIR/b.md" LINEAR_SNAPSHOT_JSON="$STUB_DIR/s.json" run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"B143"* ]]
  [[ "$output" == *"EMA-199"* ]]
}

@test "A: backlog OPEN + Linear open is fine — this is not a two-way sync" {
  # The guard asserts DONE implies closed. It deliberately does NOT assert the converse: an issue
  # closed in Linear while the backlog entry is still open is a normal mid-flight state.
  cat > "$STUB_DIR/b.md" <<'MD'
### B134 — cpu requests — **HIGH (2026-08-20)**
Linear: EMA-195.
MD
  printf '{"EMA-195":{"stateType":"backlog","state":"Backlog","project":"Weyland Lab"}}' > "$STUB_DIR/s.json"
  BACKLOG_FILE="$STUB_DIR/b.md" LINEAR_SNAPSHOT_JSON="$STUB_DIR/s.json" run bash "$GUARD"
  [ "$status" -eq 0 ]
}

@test "A: a backlog ref pointing at an issue Linear does not know is FATAL" {
  # A typo'd or deleted issue id must not read as "nothing to check".
  cat > "$STUB_DIR/b.md" <<'MD'
### B999 — ghost — **DONE (2026-08-26)**
Linear: EMA-9999.
MD
  printf '{"EMA-207":{"stateType":"completed","state":"Done","project":"Weyland Lab"}}' > "$STUB_DIR/s.json"
  BACKLOG_FILE="$STUB_DIR/b.md" LINEAR_SNAPSHOT_JSON="$STUB_DIR/s.json" run bash "$GUARD"
  [ "$status" -ne 0 ]
  [[ "$output" == *"EMA-9999"* ]]
}

# --- check B: open issue with no project ---------------------------------------------------------

@test "B: an OPEN issue with no project FAILS — the EMA-172 case" {
  # Linear holds two products on one team; project assignment is what separates them. An issue with
  # no project is invisible to BOTH filtered views while still counting in the team total. EMA-172
  # was High priority and open since 2026-08-12, and appeared in no "what's next" answer.
  cat > "$STUB_DIR/b.md" <<'MD'
### B1 — thing — **DONE (2026-08-01)**
Linear: EMA-10.
MD
  printf '{"EMA-10":{"stateType":"completed","state":"Done","project":"Weyland Lab"},"EMA-172":{"stateType":"backlog","state":"Backlog","project":null}}' > "$STUB_DIR/s.json"
  BACKLOG_FILE="$STUB_DIR/b.md" LINEAR_SNAPSHOT_JSON="$STUB_DIR/s.json" run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"EMA-172"* ]]
  [[ "$output" == *"project"* ]]
}

@test "B: a CLOSED issue with no project does NOT fail" {
  # Only open work needs to be findable. Retro-assigning projects to years of closed issues is churn.
  cat > "$STUB_DIR/b.md" <<'MD'
### B1 — thing — **DONE (2026-08-01)**
Linear: EMA-10.
MD
  printf '{"EMA-10":{"stateType":"completed","state":"Done","project":null}}' > "$STUB_DIR/s.json"
  BACKLOG_FILE="$STUB_DIR/b.md" LINEAR_SNAPSHOT_JSON="$STUB_DIR/s.json" run bash "$GUARD"
  [ "$status" -eq 0 ]
}

# --- failing closed ------------------------------------------------------------------------------

@test "an unreadable or malformed snapshot is exit 2, never a pass" {
  cat > "$STUB_DIR/b.md" <<'MD'
### B1 — thing — **DONE (2026-08-01)**
Linear: EMA-10.
MD
  BACKLOG_FILE="$STUB_DIR/b.md" LINEAR_SNAPSHOT_JSON="$STUB_DIR/missing.json" run bash "$GUARD"
  [ "$status" -eq 2 ]
  printf 'not json' > "$STUB_DIR/bad.json"
  BACKLOG_FILE="$STUB_DIR/b.md" LINEAR_SNAPSHOT_JSON="$STUB_DIR/bad.json" run bash "$GUARD"
  [ "$status" -eq 2 ]
}

@test "an EMPTY snapshot is exit 2 — 'checked nothing' is not 'found nothing'" {
  cat > "$STUB_DIR/b.md" <<'MD'
### B1 — thing — **DONE (2026-08-01)**
Linear: EMA-10.
MD
  printf '{}' > "$STUB_DIR/s.json"
  BACKLOG_FILE="$STUB_DIR/b.md" LINEAR_SNAPSHOT_JSON="$STUB_DIR/s.json" run bash "$GUARD"
  [ "$status" -eq 2 ]
}

@test "no LINEAR_API_KEY and no snapshot is exit 2 with an actionable message" {
  cat > "$STUB_DIR/b.md" <<'MD'
### B1 — thing — **DONE (2026-08-01)**
Linear: EMA-10.
MD
  BACKLOG_FILE="$STUB_DIR/b.md" LINEAR_API_KEY="" run bash "$GUARD"
  [ "$status" -eq 2 ]
  [[ "$output" == *"LINEAR_API_KEY"* ]]
}

@test "exit 1 is a finding, exit 2 is a broken guard — never conflated" {
  cat > "$STUB_DIR/b.md" <<'MD'
### B143 — thing — **DONE (2026-08-24)**
Linear: EMA-199.
MD
  printf '{"EMA-199":{"stateType":"backlog","state":"Backlog","project":"Weyland Lab"}}' > "$STUB_DIR/s.json"
  BACKLOG_FILE="$STUB_DIR/b.md" LINEAR_SNAPSHOT_JSON="$STUB_DIR/s.json" run bash "$GUARD"
  [ "$status" -eq 1 ]
  BACKLOG_FILE="$STUB_DIR/b.md" LINEAR_SNAPSHOT_JSON="$STUB_DIR/gone.json" run bash "$GUARD"
  [ "$status" -eq 2 ]
}

@test "--list prints every ref and its verdict, exit 0 even with drift" {
  cat > "$STUB_DIR/b.md" <<'MD'
### B143 — thing — **DONE (2026-08-24)**
Linear: EMA-199.
MD
  printf '{"EMA-199":{"stateType":"backlog","state":"Backlog","project":"Weyland Lab"}}' > "$STUB_DIR/s.json"
  BACKLOG_FILE="$STUB_DIR/b.md" LINEAR_SNAPSHOT_JSON="$STUB_DIR/s.json" run bash "$GUARD" --list
  [ "$status" -eq 0 ]
  [[ "$output" == *"EMA-199"* ]]
}
