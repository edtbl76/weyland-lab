#!/usr/bin/env bats
# B253 (2026-11-20) — nodes/mother/lab/weyland-platform/scripts/realm-eval.sh drives the Realm evaluation in batches:
# plan locally (realm_eval.py), run each batch in-cluster through `kubectl exec` into dagster-user-code, append the lines.
# Decisions under test: it finishes when nothing is left; a dropped exec keeps what finished and carries on; two batches
# in a row with no progress stop the loop (exit 1) instead of spinning all night; judge progress counts only VALID scores
# (a judge that keeps erroring must not look like progress); an unknown mode is exit 2. kubectl is a stub.

setup() {
  load helper
  SCRIPT="$REPO_ROOT/nodes/mother/lab/weyland-platform/scripts/realm-eval.sh"
  T="$(mktemp -d)"; mkdir -p "$T/bin" "$T/out"
  cat > "$T/tasks.json" <<'JSON'
{"questions": [{"id": "t1", "kind": "single", "q": "q1", "accept": ["saga"], "rubric": ["a"]},
               {"id": "t2", "kind": "multi", "q": "q2", "accept": ["tyr"], "rubric": ["b"]}]}
JSON
  # The stub answers like the in-cluster modes: STUB_MODE=ok (a result per item), none (no output), judge-error.
  cat > "$T/bin/kubectl" <<'SH'
#!/bin/sh
echo "$1 $2 $3 $4 $5 $6 $7 $8 $9 ${10}" >> "$STUB_DIR/kubectl.args"   # one line per call (the script arg spans many)
mode=""; for a in "$@"; do mode="$a"; done
python3 -c '
import json, sys, os
m, how = sys.argv[1], os.environ.get("STUB_MODE", "ok")
for line in sys.stdin:
    if not line.strip() or how == "none":
        continue
    i = json.loads(line)
    if m == "run":
        print(json.dumps({"id": i["id"], "arm": i["arm"], "rep": i["rep"], "kind": i["kind"], "ok": True, "answer": "x",
                          "routed_to": "saga", "wall_seconds": 1}))
    elif how == "judge-error":
        print(json.dumps({"ref": i["ref"], "ok": False, "error": "bad verdict"}))
    else:
        print(json.dumps({"ref": i["ref"], "ok": True, "met": [True], "score": 4, "reason": "r"}))
' "$mode"
SH
  chmod +x "$T/bin/kubectl"
  export PATH="$T/bin:$PATH" STUB_DIR="$T" REALM_EVAL_TASKS="$T/tasks.json" REALM_EVAL_DIR="$T/out" \
         REALM_EVAL_REPS=1 REALM_EVAL_BATCH=4
}

teardown() { rm -rf "$T"; }

@test "run: batches until every task, arm and rep is done, then stops cleanly" {
  run bash "$SCRIPT" run
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [ "$(wc -l < "$T/out/results.jsonl")" -eq 6 ]            # 2 tasks x 3 arms x 1 rep
  [ "$(wc -l < "$T/kubectl.args")" -eq 2 ]                  # batches of 4: 4 then 2
  grep -q "exec -i deploy/dagster-user-code -c dagster-user-code -- python -c" "$T/kubectl.args"
  [[ "$output" == *"nothing left"* ]]
}

@test "run: a rerun resumes and execs nothing when all is done" {
  bash "$SCRIPT" run
  : > "$T/kubectl.args"
  run bash "$SCRIPT" run
  [ "$status" -eq 0 ] && [ ! -s "$T/kubectl.args" ]
}

@test "run: no progress in two batches stops with exit 1, naming why" {
  STUB_MODE=none run bash "$SCRIPT" run
  [ "$status" -eq 1 ]
  [[ "$output" == *"no progress"* ]]
  [ "$(wc -l < "$T/kubectl.args")" -eq 2 ]
}

@test "judge: scores every successful run, then report renders a table" {
  bash "$SCRIPT" run
  run bash "$SCRIPT" judge
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [ "$(grep -c '"ok": true' "$T/out/scores.jsonl")" -eq 6 ]
  run bash "$SCRIPT" report
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  grep -q "| realm | 2 |" "$T/out/report.md" && grep -q "| single | 2 |" "$T/out/report.md"
}

@test "judge: a judge that only errors is not progress, and stops" {
  bash "$SCRIPT" run
  STUB_MODE=judge-error run bash "$SCRIPT" judge
  [ "$status" -eq 1 ]
  [[ "$output" == *"no progress"* ]]
}

@test "report before judging refuses (an unjudged success is not a score)" {
  bash "$SCRIPT" run
  run bash "$SCRIPT" report
  [ "$status" -ne 0 ]
  [[ "$output" == *"unjudged"* ]]
}

@test "an unknown mode is exit 2" {
  run bash "$SCRIPT" sweep
  [ "$status" -eq 2 ]
  [[ "$output" == *"usage"* ]]
}
