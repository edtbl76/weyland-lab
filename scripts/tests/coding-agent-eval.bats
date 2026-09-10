#!/usr/bin/env bats
# B104 — coding-agent evaluation harness (scripts/coding-agent-eval.sh).
#
# WHY THIS EXISTS: the harness scores coding agents, and the ONE way it can lie is by calling a run a
# PASS when it wasn't. Every correction in the lab's memory about silent success applies here — an
# absent result must never stand for success; a tool's exit code is not its verdict; a fixture that
# was not actually failing is not a real task. So the decision logic is tested directly, with
# fail-closed as the property under test:
#
#   - PASS only when the grader prints `GRADE: PASS` as its verdict line.
#   - No verdict line at all  -> ERROR (never PASS).
#   - Fixture already passing before the agent ran -> RED-BROKEN (never PASS).
#   - Agent overruns the task timeout -> TIMEOUT (never PASS).
#   - The recorded TSV `pass` column is 1 ONLY for a clean PASS.
#
# Graders here are bash-only (a flag file), so CI needs nothing but python3 (already added to the
# shell-tests step to read the agents.json manifest) — no node/python toolchain per language.

setup() {
  load helper
  SCRIPT="$REPO_ROOT/scripts/coding-agent-eval.sh"
  ROOT="$BATS_TEST_TMPDIR/eval"
  TASKS="$ROOT/tasks"
  AGENTS="$ROOT/agents.json"
  OUT="$ROOT/out.tsv"
  mkdir -p "$TASKS"
  _write_agents
  _make_flag_task flag-normal FAIL 600     # grader: PASS iff state==fixed
  _make_flag_task flag-alwayspass PASS 600 # grader always PASS -> Red pre-check trips
  _make_slow_task slow 1                    # 1s timeout, grader always FAIL
  _make_noverdict_task noverdict 600        # FAIL while bug, NO verdict once fixed
}

# --- synthetic fixtures --------------------------------------------------------------------------

_write_agents() {
  cat >"$AGENTS" <<'JSON'
{
  "agents": {
    "fixer": "printf fixed > state",
    "noop": "true",
    "sleeper": "sleep 3"
  }
}
JSON
}

# A task whose grader reads workdir/state: PASS when it contains "fixed", else FAIL.
# $2 seeds the initial state as bug(FAIL) or fixed(PASS) so we can force a Red-broken fixture.
_make_flag_task() {
  local id="$1" seed="$2" to="$3" d="$TASKS/$1"
  mkdir -p "$d/workdir"
  if [ "$seed" = "PASS" ]; then echo fixed >"$d/workdir/state"; else echo bug >"$d/workdir/state"; fi
  printf 'fix it\n' >"$d/task.md"
  printf '{"id":"%s","timeout_s":%s}\n' "$id" "$to" >"$d/meta.json"
  cat >"$d/grade.sh" <<'SH'
set -uo pipefail
if [ -f state ] && grep -q fixed state; then echo "GRADE: PASS"; exit 0; fi
echo "GRADE: FAIL"; exit 1
SH
}

# A task with a short timeout and a grader that always FAILs — for the timeout path.
_make_slow_task() {
  local id="$1" to="$2" d="$TASKS/$1"
  mkdir -p "$d/workdir"; printf 'slow\n' >"$d/task.md"
  printf '{"id":"%s","timeout_s":%s}\n' "$id" "$to" >"$d/meta.json"
  cat >"$d/grade.sh" <<'SH'
echo "GRADE: FAIL"; exit 1
SH
}

# A task whose grader FAILs while state==bug but prints NO verdict once state==fixed — exercises the
# GREEN-time ERROR path (grader produced no GRADE line) distinct from the Red pre-check.
_make_noverdict_task() {
  local id="$1" to="$2" d="$TASKS/$1"
  mkdir -p "$d/workdir"; echo bug >"$d/workdir/state"
  printf 'fix it\n' >"$d/task.md"
  printf '{"id":"%s","timeout_s":%s}\n' "$id" "$to" >"$d/meta.json"
  cat >"$d/grade.sh" <<'SH'
if grep -q fixed state 2>/dev/null; then echo "grader crashed, no verdict"; exit 0; fi
echo "GRADE: FAIL"; exit 1
SH
}

run_eval() { EVAL_TASKS_DIR="$TASKS" EVAL_AGENTS_FILE="$AGENTS" EVAL_OUT="$OUT" run bash "$SCRIPT" "$@"; }
tsv_field() { # tsv_field <agent> <task> <colname>  -> value from the recorded row
  python3 - "$OUT" "$1" "$2" "$3" <<'PY'
import csv,sys
out,agent,task,col=sys.argv[1:5]
for r in csv.DictReader(open(out),delimiter='\t'):
    if r["agent"]==agent and r["task"]==task: print(r[col]); break
PY
}

# --- the harness exists and lists ----------------------------------------------------------------

@test "script exists" { [ -f "$SCRIPT" ]; }

@test "--list shows agents and tasks" {
  run_eval --list
  [ "$status" -eq 0 ]
  [[ "$output" == *"fixer"* ]]
  [[ "$output" == *"flag-normal"* ]]
}

# --- end-to-end decision paths -------------------------------------------------------------------

@test "fixer on a normal task PASSES and records pass=1" {
  run_eval --agent fixer --task flag-normal
  [ "$status" -eq 0 ]
  [[ "$output" == *"flag-normal  PASS"* ]]
  [ "$(tsv_field fixer flag-normal result)" = "PASS" ]
  [ "$(tsv_field fixer flag-normal pass)" = "1" ]
}

@test "noop on a normal task FAILS and records pass=0" {
  run_eval --agent noop --task flag-normal
  [[ "$output" == *"flag-normal  FAIL"* ]]
  [ "$(tsv_field noop flag-normal result)" = "FAIL" ]
  [ "$(tsv_field noop flag-normal pass)" = "0" ]
}

@test "a fixture that already passes is RED-BROKEN, never a free pass" {
  run_eval --agent fixer --task flag-alwayspass
  [[ "$output" == *"RED-BROKEN"* ]]
  # No TSV row is written for a broken fixture (nothing was actually evaluated).
  [ -z "$(tsv_field fixer flag-alwayspass result)" ]
}

@test "an agent that overruns the task timeout is TIMEOUT, never a pass" {
  run_eval --agent sleeper --task slow
  [[ "$output" == *"TIMEOUT"* ]]
  [ "$(tsv_field sleeper slow result)" = "TIMEOUT" ]
  [ "$(tsv_field sleeper slow pass)" = "0" ]
}

@test "a grader that prints no verdict after the agent runs is ERROR, never a pass" {
  run_eval --agent fixer --task noverdict
  [[ "$output" == *"ERROR"* ]]
  [ "$(tsv_field fixer noverdict result)" = "ERROR" ]
  [ "$(tsv_field fixer noverdict pass)" = "0" ]
}

@test "selecting an unknown agent is a loud error" {
  run_eval --agent nope --task flag-normal
  [ "$status" -ne 0 ]
  [[ "$output" == *"not in manifest"* ]]
}

@test "no agent selected is a loud error, not a silent no-op" {
  run_eval --task flag-normal
  [ "$status" -eq 2 ]
  [[ "$output" == *"no agent selected"* ]]
}

# --- grade() unit tests via the lib seam (fail-closed classification) ----------------------------

lib_source() { CODING_AGENT_EVAL_LIB=1 EVAL_AGENTS_FILE="$AGENTS" EVAL_TASKS_DIR="$TASKS" source "$SCRIPT"; }

_grader_dir() { # _grader_dir <body> -> prints a dir containing grade.sh with that body
  local d; d="$(mktemp -d "$BATS_TEST_TMPDIR/g.XXXXXX")"
  printf '%s\n' "$1" >"$d/grade.sh"
  printf '%s' "$d"
}

@test "grade(): GRADE: PASS classifies PASS" {
  lib_source
  d="$(_grader_dir 'echo "GRADE: PASS"; exit 0')"
  [ "$(grade "$d" "$d/grade.sh")" = "PASS" ]
}

@test "grade(): GRADE: FAIL classifies FAIL" {
  lib_source
  d="$(_grader_dir 'echo "GRADE: FAIL"; exit 1')"
  [ "$(grade "$d" "$d/grade.sh")" = "FAIL" ]
}

@test "grade(): no verdict line classifies ERROR even on exit 0" {
  lib_source
  d="$(_grader_dir 'echo "ran some things"; exit 0')"
  [ "$(grade "$d" "$d/grade.sh")" = "ERROR" ]
}

@test "grade(): a spoofed PASS in body text does not win over the real FAIL verdict" {
  # A grader could echo the words GRADE: PASS mid-output; only a full verdict LINE counts, and the
  # LAST one wins. Here the real verdict is FAIL.
  lib_source
  d="$(_grader_dir 'echo "not GRADE: PASS yet"; echo "GRADE: FAIL"; exit 1')"
  [ "$(grade "$d" "$d/grade.sh")" = "FAIL" ]
}

@test "task_timeout() reads meta.json and defaults to 600" {
  lib_source
  [ "$(task_timeout "$TASKS/slow")" = "1" ]
  nometa="$(mktemp -d "$BATS_TEST_TMPDIR/nm.XXXXXX")"
  [ "$(task_timeout "$nometa")" = "600" ]
}
