#!/usr/bin/env bash
# Judge ONE finished trial with its task's hidden reference judge (validated: passes the real solution, fails the base).
#   usage: judge_trial.sh <small|brown|green> <arm>      → results/<task>-<arm>.judge  (last line: JUDGE: PASS|FAIL ...)
# The trial repo is mounted read-only; every judge runs in a throwaway container.
set -uo pipefail
task="$1"; arm="$2"; suf="${3:-}"   # optional replicate suffix
B="${SDD_BAKEOFF_HOME:-/home/edwardmangini/sdd-bakeoff}"   # work dir: trials, results, toolbox (outside the repo)
C="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # harness code: eval/sdd-bakeoff in the repo
D="$B/trials/$task-$arm$suf"
OUT="$B/results/$task-$arm$suf.judge"
case "$task" in
  small)
    docker run --rm -e TRIAL=/trial -v "$D":/trial:ro -v "$C/reference/judge-small":/judge:ro --entrypoint sh bats/bats:latest \
      -c 'apk add --no-cache python3 py3-yaml prometheus >/dev/null 2>&1; sh /judge/judge.sh' > "$OUT" 2>&1 ;;
  brown)
    docker run --rm -e TRIAL=/trial -v "$D":/trial:ro -v "$C/reference/judge-brown":/judge:ro --entrypoint sh bats/bats:latest \
      -c 'apk add --no-cache python3 py3-yaml >/dev/null 2>&1; bats /judge/judge.bats; echo "BATS_EXIT=$?"' > "$OUT" 2>&1
    pass=$(grep -c "^ok " "$OUT"); fail=$(grep -c "^not ok " "$OUT")
    if grep -q "BATS_EXIT=0" "$OUT" && [ "$fail" -eq 0 ] && [ "$pass" -gt 0 ]; then
      echo "JUDGE: PASS ($pass/$((pass + fail)) cases)" >> "$OUT"
    else
      echo "JUDGE: FAIL ($pass/$((pass + fail)) cases)" >> "$OUT"
    fi ;;
  green)
    S="$D/nodes/mother/lab/weyland-platform/services/store-scaler"
    if [ ! -f "$S/app.py" ]; then
      echo "JUDGE: FAIL (no services/store-scaler/app.py)" > "$OUT"
    else
      docker run --rm -e SERVICE_DIR=/svc -v "$S":/svc:ro -v "$C/reference/judge-green":/judge:ro python:3.12-slim \
        sh -c 'pip install -q --disable-pip-version-check -r /svc/requirements.txt >/tmp/i 2>&1 || { echo "requirements install failed:"; tail -3 /tmp/i; }; pip install -q --disable-pip-version-check httpx pytest >/dev/null 2>&1; cd /tmp && python -m pytest -q -p no:cacheprovider /judge/test_contract.py 2>&1 | tail -15' > "$OUT" 2>&1
      if grep -qE "^[0-9]+ passed" "$OUT" && ! grep -qE "[0-9]+ (failed|error)" "$OUT"; then
        echo "JUDGE: PASS ($(grep -oE '^[0-9]+ passed' "$OUT"))" >> "$OUT"
      else
        echo "JUDGE: FAIL ($(grep -oE '[0-9]+ (passed|failed|errors?)' "$OUT" | tr '\n' ' '))" >> "$OUT"
      fi
    fi ;;
  vague)
    # the brief named no interface: judge.py finds the CI checks the trial added and runs them on planted copies
    MODE="${JUDGE_MODE:-round1}"
    docker run --rm -v "$D":/src:ro -v "$C/reference/judge-vague":/j:ro --entrypoint sh bats/bats:latest -c \
      'apk add --no-cache python3 py3-yaml jq git prometheus >/dev/null 2>&1; cp -r /src /w && git config --global --add safe.directory /w && cd /w && python3 /j/judge.py /w "$(git rev-list --max-parents=0 HEAD)" '"$MODE" > "$OUT" 2>&1 ;;
  *) echo "unknown task $task"; exit 2 ;;
esac
tail -1 "$OUT"
