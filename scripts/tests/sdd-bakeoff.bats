#!/usr/bin/env bats
# B86 bake-off harness (eval/sdd-bakeoff): the decisions that went wrong during the bake-off, pinned.
# - cost accounting: total_cost_usd is cumulative over a session, also across --resume; turns are per process
# - the AI-DLC 2.11 click-through driver stops on TRIAL DONE, on a final TRIAL BLOCKED, and on a no-progress reply
# - fail closed: a vague trial with no own tests found is never "own tests pass"; a review with no answer is a miss
# - the docs ablation excludes a pair whose base passes, by the LAST verdict line
# - the exact statistics (McNemar, sign-flip, Holm, stratified permutation) on hand-checkable inputs
# Everything runs on fixtures under $BATS_TEST_TMPDIR; no agent, no docker, no network.

H="$BATS_TEST_DIRNAME/../../eval/sdd-bakeoff"

setup() {
  W="$BATS_TEST_TMPDIR/work"
  mkdir -p "$W/results" "$W/toolbox/bin" "$W/claude-config"
  export SDD_BAKEOFF_HOME="$W"
}

# a result event line; $1 = result text, $2 = cumulative cost, $3 = turns
ev() { printf '{"type":"result","session_id":"s1","result":"%s","total_cost_usd":%s,"num_turns":%s,"duration_ms":1000,"modelUsage":{"m":{"outputTokens":10,"inputTokens":1}}}\n' "$1" "$2" "$3"; }
marker() { printf '{"type":"bakeoff_process"}\n'; }

stats() {  # run_stats(<log>) → "cost turns procs"
  python3 -c '
import sys
src = open(sys.argv[1] + "/summarize.py").read()
sys.argv = ["summarize", sys.argv[2]]
exec(src[:src.index("\nrows = []")])
s = run_stats(sys.argv[1])
print(s["cost"], s["turns"], s["procs"])' "$H" "$1"
}

@test "an undriven log: cost is the LAST result (cumulative), turns are summed" {
  { ev "partial" 1.0 5; ev "TRIAL DONE" 1.5 3; } > "$W/a.jsonl"
  run stats "$W/a.jsonl"
  [ "$status" -eq 0 ]
  [ "$output" = "1.5 8 1" ]
}

@test "a driven log is counted only up to its first final status" {
  { marker; ev "Reply with a number" 0.5 4; marker; ev "TRIAL BLOCKED: no docker" 2.0 10;
    marker; ev "TRIAL BLOCKED: no docker" 2.1 1; marker; ev "TRIAL BLOCKED: no docker" 2.2 1; } > "$W/d.jsonl"
  run stats "$W/d.jsonl"
  [ "$status" -eq 0 ]
  [ "$output" = "2.0 14 2" ]
}

@test "a gate question that mentions TRIAL BLOCKED is not a final status" {
  { marker; ev "TRIAL BLOCKED until you choose. Reply with a number" 0.5 4; marker; ev "TRIAL DONE" 1.0 6; } > "$W/g.jsonl"
  run stats "$W/g.jsonl"
  [ "$output" = "1.0 10 2" ]
}

# ---- the click-through driver (run_trial.sh), with a stub claude ------------------------------------------------------

stub_claude() {  # $@ = the result text for each successive process
  S="$BATS_TEST_TMPDIR/stub"; mkdir -p "$S"
  printf '%s\n' "$@" > "$S/script"
  : > "$S/n"
  cat > "$S/claude" <<'STUB'
#!/bin/sh
d=$(dirname "$0"); n=$(($(wc -l < "$d/n") + 1)); echo x >> "$d/n"
text=$(sed -n "${n}p" "$d/script"); [ -n "$text" ] || text="(stub ran out)"
printf '{"type":"system","subtype":"init","session_id":"s1"}\n'
printf '{"type":"result","session_id":"s1","result":"%s","total_cost_usd":%s,"num_turns":1}\n' "$text" "$n"
STUB
  chmod +x "$S/claude"
  export CLAUDE_BIN="$S/claude"
}

trial() {  # trial <arm> → runs run_trial.sh small <arm> on an empty git repo; prints human_replies
  mkdir -p "$W/trials/small-$1"
  git -C "$W/trials/small-$1" init -q
  bash "$H/run_trial.sh" small "$1" > /dev/null 2>&1
  sed -n 's/^human_replies=//p' "$W/results/small-$1.meta"
}

@test "driver: replies until TRIAL DONE, then stops" {
  stub_claude "Approve? Reply with a number" "Next gate. Reply with a number" "TRIAL DONE"
  run trial aidlc211
  [ "$output" = "2" ]
  [ "$(wc -l < "$S/n")" -eq 3 ]
}

@test "driver: a final TRIAL BLOCKED stops it (no 15 wasted replies)" {
  stub_claude "Approve? Reply with a number" "TRIAL BLOCKED: no docker socket" "TRIAL BLOCKED: no docker socket"
  run trial aidlc211
  [ "$output" = "1" ]
  [ "$(wc -l < "$S/n")" -eq 2 ]
}

@test "driver: a reply that changes nothing stops it" {
  stub_claude "Same question. Reply with a number" "Same question. Reply with a number" "TRIAL DONE"
  run trial aidlc211
  [ "$output" = "1" ]
}

@test "driver: every other arm gets the single prompt only" {
  stub_claude "Approve? Reply with a number" "TRIAL DONE"
  run trial openspec
  [ "$output" = "0" ]
  [ "$(wc -l < "$S/n")" -eq 1 ]
}

# ---- fail closed -------------------------------------------------------------------------------------------------------

@test "intent oracle: a vague trial with no own tests found is never 'own tests pass'" {
  run python3 -c '
import sys
__file__ = sys.argv[1] + "/select_intent.py"
src = open(__file__).read()
exec(src[:src.index("\nids = ")])
print(own_tests_pass("/nonexistent", "vague", []))' "$H"
  [ "$status" -eq 0 ]
  [ "$output" = "False" ]
}

@test "oracle scoring: a review with no DEFECT LINE is a miss, a bolded one parses" {
  mkdir -p "$W/results/oracle"
  printf 'task\tarm\tvariant\ttarget\tdefect\tline\nsmall\tnone\tnodocs\tf.py\td\t10\nsmall\tbmad\tdocs\tf.py\td\t10\n' > "$W/results/oracle/cases.tsv"
  ev "I could not tell." 0.2 3 > "$W/results/oracle/small-none-nodocs.jsonl"
  ev "Found it. **DEFECT LINE: 11**" 0.2 3 > "$W/results/oracle/small-bmad-docs.jsonl"
  run python3 "$H/score_reviews.py"
  [ "$status" -eq 0 ]
  run cut -f5,6 "$W/results/oracle/scores.tsv"
  [ "${lines[1]}" = "none	0" ]
  [ "${lines[2]}" = "11	1" ]
}

@test "ablation: a base judge whose LAST verdict is FAIL does not exclude the pair" {
  printf 'JUDGE: PASS (suite green, plant refused)\nok 1 plant\nJUDGE: FAIL (round-1 exit 0, empty plant exit 0)\n' > "$W/b.judge"
  printf 'JUDGE: FAIL (x)\nJUDGE: PASS (16/16)\n' > "$W/p.judge"
  run python3 -c '
import sys
fail_last, pass_last = sys.argv[2], sys.argv[3]   # read first: analyze.py resets sys.argv in its prelude
__file__ = sys.argv[1] + "/analyze.py"
src = open(__file__).read()
exec(src[:src.index("\nout = []")])
print(base_passes(fail_last), base_passes(pass_last), base_passes("/nonexistent"))' "$H" "$W/b.judge" "$W/p.judge"
  [ "$status" -eq 0 ]
  [ "$output" = "False True False" ]
}

# ---- the exact statistics ----------------------------------------------------------------------------------------------

@test "statistics: McNemar, sign-flip, Holm and the stratified permutation are exact" {
  run python3 -c '
import math, sys
s = open(sys.argv[1] + "/score_reviews.py").read()
ns = {"math": math}
exec(s[s.index("def mcnemar_exact"):s.index("\nrows, out")], ns)
__file__ = sys.argv[1] + "/analyze.py"
a = open(__file__).read()
exec(a[:a.index("\nout = []")])
print(ns["mcnemar_exact"](0, 6), ns["mcnemar_exact"](3, 3))
print(sign_flip([1.0, 1.0, 1.0]), [round(x, 3) for x in holm([0.01, 0.04, 0.03])])
runs = [{"task": t, "arm": a, "cost": c} for t in TASKS for a, c in (("none", 1), ("none", 1), ("x", 9), ("x", 9))]
e, p, na, nn = strat_perm(runs, "x", "cost")
print(e, round(p, 4), na, nn)' "$H"
  [ "$status" -eq 0 ]
  [ "${lines[0]}" = "0.03125 1.0" ]
  [ "${lines[1]}" = "0.25 [0.03, 0.06, 0.06]" ]
  # 4 tasks, each 2 vs 2: 6 labelings per task, 6^4 = 1296 combinations, 2 as extreme (all-x-high, all-x-low)
  [ "${lines[2]}" = "8 0.0015 8 8" ]
}
