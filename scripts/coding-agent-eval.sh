#!/usr/bin/env bash
# B104 — coding-agent evaluation harness. Scores the lab's coding agents on a
# suite of self-contained tasks: each task ships buggy code + a FAILING stdlib
# test; an agent is given the task prompt in an isolated copy of the workdir and
# must make the test pass. We record pass/fail + wall-clock duration per
# (agent, task) to a committed baseline, the way scripts/perf-baseline.sh records
# throughput. ON-DEMAND ONLY — a real-agent run spends API quota and minutes;
# NEVER wire this into CI or a schedule.
#
# Grading is FAIL-CLOSED (see the lab's silent-failure corrections): a task
# passes ONLY when its grader prints `GRADE: PASS` as its verdict line. A run
# that errors, times out, prints no verdict, or whose fixture was not failing
# BEFORE the agent ran (the Red pre-check) is never scored as a pass.
#
#   Usage:
#     scripts/coding-agent-eval.sh --list
#     scripts/coding-agent-eval.sh --agent mock-pass --task py-median-bug
#     scripts/coding-agent-eval.sh --agent claude,opencode --all
#     scripts/coding-agent-eval.sh --all-agents --all          # every real+mock agent x every task
#   Env: PERF... no; EVAL_OUT (baseline file), EVAL_TASKS_DIR, EVAL_AGENTS_FILE.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TASKS_DIR="${EVAL_TASKS_DIR:-$REPO_ROOT/eval/coding-agents/tasks}"
AGENTS_FILE="${EVAL_AGENTS_FILE:-$REPO_ROOT/eval/coding-agents/agents.json}"
OUT="${EVAL_OUT:-$REPO_ROOT/tests/eval/coding-agents.tsv}"

die() { printf 'error: %s\n' "$*" >&2; exit 2; }
command -v python3 >/dev/null 2>&1 || die "python3 not found (needed to read $AGENTS_FILE)"
[ -f "$AGENTS_FILE" ] || die "agents manifest not found: $AGENTS_FILE"
[ -d "$TASKS_DIR" ]   || die "tasks dir not found: $TASKS_DIR"

# ---- agent manifest -------------------------------------------------------
agent_names() {
  python3 -c 'import json,sys; print("\n".join(json.load(open(sys.argv[1]))["agents"].keys()))' "$AGENTS_FILE"
}
agent_cmd() {
  python3 -c 'import json,sys; a=json.load(open(sys.argv[1]))["agents"]; sys.exit(3) if sys.argv[2] not in a else print(a[sys.argv[2]])' \
    "$AGENTS_FILE" "$1"
}

# ---- task discovery -------------------------------------------------------
task_ids() {
  local d
  for d in "$TASKS_DIR"/*/; do
    [ -f "$d/task.md" ] && [ -f "$d/grade.sh" ] && [ -d "$d/workdir" ] && basename "$d"
  done
}
task_timeout() {  # task_dir -> timeout seconds (default 600)
  local m="$1/meta.json"
  [ -f "$m" ] && python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("timeout_s",600))' "$m" 2>/dev/null || echo 600
}

# ---- grading (fail-closed) -----------------------------------------------
# Runs the grader in $1 (the run workdir) and echoes exactly one of:
#   PASS | FAIL | ERROR   (ERROR = grader produced no GRADE: verdict line)
grade() {
  local rundir="$1" gradesh="$2" out verdict
  out="$(cd "$rundir" && bash "$gradesh" 2>&1)"
  # The verdict is the LAST GRADE: line the grader printed. No line => ERROR.
  verdict="$(printf '%s\n' "$out" | grep -E '^GRADE: (PASS|FAIL)$' | tail -1)"
  case "$verdict" in
    "GRADE: PASS") echo PASS ;;
    "GRADE: FAIL") echo FAIL ;;
    *)             echo ERROR ;;
  esac
}

# ---- run one (agent, task) ------------------------------------------------
run_one() {
  local agent="$1" task="$2" cmd="$3"
  local tdir="$TASKS_DIR/$task" gradesh="$TASKS_DIR/$task/grade.sh"
  local to; to="$(task_timeout "$tdir")"
  local rundir; rundir="$(mktemp -d "${TMPDIR:-/tmp}/cae-${agent}-${task}.XXXXXX")"
  cp -a "$tdir/workdir/." "$rundir/" || { rm -rf "$rundir"; echo "ERROR"; return; }

  # Make the run workdir a throwaway git repo. This models "here is a repo, fix
  # the bug" and satisfies agents that refuse to run outside a trusted git dir
  # (codex needs this, or --skip-git-repo-check). Best-effort — the eval still
  # works without git for agents that don't require it.
  if command -v git >/dev/null 2>&1; then
    ( cd "$rundir" \
        && git init -q \
        && git add -A \
        && git -c user.email=eval@weyland.lab -c user.name=coding-agent-eval commit -qm seed ) >/dev/null 2>&1 || true
  fi

  # Red pre-check: the fixture MUST fail before the agent touches it. A fixture
  # that already passes is broken (or the test is a no-op) — never a free pass.
  local red; red="$(grade "$rundir" "$gradesh")"
  if [ "$red" != "FAIL" ]; then
    rm -rf "$rundir"; echo "RED-BROKEN"; return
  fi

  # Run the agent in the isolated copy, bounded by the task timeout.
  local prompt start end dur rc
  prompt="$(cat "$tdir/task.md")"
  start="$(date +%s)"
  # stdin MUST be /dev/null: the caller loops over tasks with `while read ...`,
  # and an agent that reads stdin (codex appends piped stdin to its prompt as a
  # <stdin> block) would both pollute its prompt AND swallow the loop's
  # remaining task lines — which silently dropped every task after the first.
  ( cd "$rundir" && PROMPT="$prompt" TASK_DIR="$tdir" TASK_ID="$task" \
      timeout "$to" bash -c "$cmd" </dev/null ) >"$rundir/.agent.log" 2>&1
  rc=$?
  end="$(date +%s)"; dur=$(( end - start ))

  local result
  # `timeout` signals a kill differently across implementations: GNU coreutils
  # exits 124; busybox (Alpine/CI) TERMs the child and exits 143 (128+15), or
  # 137 (128+9) with -k. Treat all three as TIMEOUT so the verdict is the same
  # on the dev box and in CI.
  if [ "$rc" -eq 124 ] || [ "$rc" -eq 143 ] || [ "$rc" -eq 137 ]; then
    result="TIMEOUT"
  else
    result="$(grade "$rundir" "$gradesh")"   # PASS | FAIL | ERROR
  fi
  # pass boolean: 1 ONLY for a clean PASS
  local pass=0; [ "$result" = "PASS" ] && pass=1
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$agent" "$task" "$pass" "$result" "$dur" "$rc" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$OUT"
  RESULT_LINE="$agent  $task  $result  ${dur}s  (agent rc=$rc)"
  rm -rf "$rundir"
  echo "$result"
}

# When sourced with CODING_AGENT_EVAL_LIB=1, expose the functions above (grade,
# run_one, task_timeout, …) for unit tests and stop before the arg-parsing /
# run body below. Mirrors check-linear-sync.sh's LINEAR_SYNC_LIB seam.
[ -n "${CODING_AGENT_EVAL_LIB:-}" ] && return 0

# ---- arg parsing ----------------------------------------------------------
SEL_AGENTS=""; SEL_TASKS=""; DO_ALL_TASKS=0; DO_ALL_AGENTS=0; DO_LIST=0
while [ $# -gt 0 ]; do
  case "$1" in
    --list)       DO_LIST=1; shift ;;
    --agent)      SEL_AGENTS="$SEL_AGENTS,${2:?--agent needs a value}"; shift 2 ;;
    --task)       SEL_TASKS="$SEL_TASKS,${2:?--task needs a value}"; shift 2 ;;
    --all|--all-tasks) DO_ALL_TASKS=1; shift ;;
    --all-agents) DO_ALL_AGENTS=1; shift ;;
    -h|--help)    grep -E '^#( |$)' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)            die "unknown arg: $1 (try --help)" ;;
  esac
done

if [ "$DO_LIST" -eq 1 ]; then
  echo "agents:"; agent_names | sed 's/^/  - /'
  echo "tasks:";  task_ids   | sed 's/^/  - /'
  exit 0
fi

# Resolve the agent + task selections as NEWLINE-delimited strings, never bash
# arrays: referencing an empty array under `set -u` is an "unbound variable"
# error on bash < 4.4 (the dev box), and it silently skipped the emptiness
# guard here — a no-agent run must fail loudly, not fall through to 0/0 exit 0.
ALL_TASKS="$(task_ids)"
[ -n "$ALL_TASKS" ] || die "no tasks discovered under $TASKS_DIR"

# select_lines <all-newline-list> <comma-selection> <do-all-flag> -> newline list
select_lines() {
  local all="$1" sel="$2" doall="$3" tok out=""
  if [ "$doall" -eq 1 ]; then printf '%s\n' "$all"; return; fi
  IFS=',' read -r -a _req <<< "${sel#,}"
  for tok in ${_req[@]+"${_req[@]}"}; do
    [ -n "$tok" ] && out="${out}${tok}"$'\n'
  done
  printf '%s' "$out"
}

AGENTS="$(select_lines "$(agent_names)" "$SEL_AGENTS" "$DO_ALL_AGENTS")"
[ -n "$AGENTS" ] || die "no agent selected (use --agent NAME or --all-agents; --list to see names)"
TASKS="$(select_lines "$ALL_TASKS" "$SEL_TASKS" "$DO_ALL_TASKS")"
[ -n "$TASKS" ] || die "no task selected (use --task ID or --all; --list to see ids)"

mkdir -p "$(dirname "$OUT")"
[ -f "$OUT" ] || printf 'agent\ttask\tpass\tresult\tduration_s\tagent_rc\ttimestamp\n' > "$OUT"

total=0; passed=0
while IFS= read -r agent; do
  [ -n "$agent" ] || continue
  cmd="$(agent_cmd "$agent")" || die "agent '$agent' not in manifest (--list to see names)"
  while IFS= read -r task; do
    [ -n "$task" ] || continue
    printf '→ %s × %s ...\n' "$agent" "$task"
    RESULT_LINE=""
    res="$(run_one "$agent" "$task" "$cmd")"
    total=$(( total + 1 )); [ "$res" = "PASS" ] && passed=$(( passed + 1 ))
    printf '  %s\n' "${RESULT_LINE:-$agent  $task  $res}"
  done <<< "$TASKS"
done <<< "$AGENTS"

printf '\n%d/%d passed\n' "$passed" "$total"
printf 'baseline → %s\n' "$OUT"
# Non-zero exit if nothing passed AND real agents were asked (a full miss is a
# signal, not silent success). Mock-only smoke of the harness still exits 0.
if [ "$passed" -eq 0 ] && [ "$DO_ALL_AGENTS" -eq 1 ]; then exit 1; fi
exit 0
