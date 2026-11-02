#!/usr/bin/env bash
# Run ONE follow-on change (layer 2) with plain Claude Code on trials2/<task>-<arm>, then judge it.
#   usage: run_followon.sh <task> <arm>   → results2/<task>-<arm>.{jsonl,err,meta,judge}
# Identical for every arm: model, prompt, sandbox/permissions, no MCP, fresh config, caps. Only the repo differs.
set -uo pipefail
task="$1"; arm="$2"
B="${SDD_BAKEOFF_HOME:-/home/edwardmangini/sdd-bakeoff}"   # work dir: trials, results, toolbox (outside the repo)
C="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # harness code: eval/sdd-bakeoff in the repo
D="$B/${TRIALS_DIR:-trials2}/$task-$arm"   # TRIALS_DIR=trials3 for the docs ablation
RES="$B/${RESULTS_DIR:-results2}"
mkdir -p "$RES"
OUT="$RES/$task-$arm"
[ -d "$D" ] || { echo "no follow-on repo $D"; exit 2; }
if [ -n "${BASE_CHECK:-}" ]; then
  # BASE_CHECK=1: judge the follow-on repo as built, with no agent run → $OUT.base.judge. A clean base must FAIL the
  # follow-on judge; a PASS means the answer is already in the repo (the 2026-11-01 ablation contamination).
  OUT="$RES/$task-$arm.base"; rc=-
else
[ -e "$OUT.jsonl" ] && { echo "already ran: $OUT.jsonl"; exit 2; }
prompt="Complete the change request in TASK.md directly, with no spec-driven framework. You are working UNATTENDED: nobody will read or answer you until you finish; make reasonable choices and continue. Use only the tools on PATH (see TASK.md). Do not run git commit or git push. Stop when every acceptance criterion in TASK.md is met, or when you are truly blocked. End with a line 'TRIAL DONE' or 'TRIAL BLOCKED: <reason>', then a short summary of what you changed."
T="$B/toolbox"; TMP="$B/tmp-${RESULTS_DIR:-results2}/$task-$arm"; mkdir -p "$TMP"
start=$(date -u +%FT%TZ)
cd "$D" || exit 2
env -i HOME="$HOME" USER="${USER:-$(id -un)}" LANG=C.UTF-8 TERM=dumb \
  PATH="$T/bin:$T/venv/bin:/usr/local/bin:/usr/bin:/bin" \
  CLAUDE_CONFIG_DIR="$B/claude-config" TMPDIR="$TMP" \
  npm_config_cache="$TMP/npm" PIP_CACHE_DIR="$TMP/pip" UV_CACHE_DIR="$TMP/uv" XDG_CACHE_HOME="$TMP/xdg" \
  timeout 3600 /home/edwardmangini/.local/bin/claude -p "$prompt" \
    --model claude-opus-5-5 --max-turns 250 \
    --settings "$C/sandbox-settings.json" --strict-mcp-config --mcp-config "$C/no-mcp.json" \
    --permission-mode dontAsk --allowedTools "Read,Edit,Write,Bash,Glob,Grep,Task,TodoWrite" --permission-prompts none \
    --output-format stream-json --verbose > "$OUT.jsonl" 2> "$OUT.err"
rc=$?
{ echo "task=$task arm=$arm (follow-on, plain agent) exit=$rc"; echo "start=$start end=$(date -u +%FT%TZ) exit=$rc"
  echo "files_changed=$(git -C "$D" status --porcelain | wc -l)"; git -C "$D" status --porcelain | head -40; } > "$OUT.meta"
fi
R="$C/reference"
case "$task" in
  small) docker run --rm -e TRIAL=/trial -v "$D":/trial:ro -v "$R":/ref:ro --entrypoint sh bats/bats:latest \
           -c 'apk add --no-cache python3 py3-yaml prometheus >/dev/null 2>&1; sh /ref/judge2-small/judge.sh' > "$OUT.judge" 2>&1 ;;
  brown) docker run --rm -e TRIAL=/trial -v "$D":/trial:ro -v "$R":/ref:ro --entrypoint sh bats/bats:latest \
           -c 'apk add --no-cache python3 py3-yaml >/dev/null 2>&1; bats /ref/judge-brown/judge.bats /ref/judge2-brown/judge2.bats; echo "BATS_EXIT=$?"' > "$OUT.judge" 2>&1
         p=$(grep -c "^ok " "$OUT.judge"); f=$(grep -c "^not ok " "$OUT.judge")
         if grep -q "BATS_EXIT=0" "$OUT.judge" && [ "$f" -eq 0 ]; then echo "JUDGE: PASS ($p/$((p+f)))" >> "$OUT.judge"; else echo "JUDGE: FAIL ($p/$((p+f)))" >> "$OUT.judge"; fi ;;
  green) S="$D/nodes/mother/lab/weyland-platform/services/store-scaler"
         docker run --rm -e SERVICE_DIR=/svc -v "$S":/svc:ro -v "$R":/ref:ro python:3.12-slim sh -c \
           'pip install -q --disable-pip-version-check -r /svc/requirements.txt httpx pytest >/dev/null 2>&1; cd /tmp; python -m pytest -q -p no:cacheprovider /ref/judge-green/test_contract.py 2>&1 | tail -1; python -m pytest -q -p no:cacheprovider /ref/judge2-green/test_followon.py 2>&1 | tail -1' > "$OUT.judge" 2>&1
         if ! grep -qE "[0-9]+ (failed|error)" "$OUT.judge" && [ "$(grep -cE '^[0-9]+ passed' "$OUT.judge")" -eq 2 ]; then echo "JUDGE: PASS (round-1 10 + follow-on 4)" >> "$OUT.judge"; else echo "JUDGE: FAIL ($(tr '\n' ' ' < "$OUT.judge" | cut -c1-120))" >> "$OUT.judge"; fi ;;
  vague) docker run --rm -v "$D":/src:ro -v "$R/judge-vague":/j:ro --entrypoint sh bats/bats:latest -c \
      'apk add --no-cache python3 py3-yaml jq git prometheus >/dev/null 2>&1; cp -r /src /w && git config --global --add safe.directory /w && cd /w && python3 /j/judge.py /w "$(git rev-list --max-parents=0 HEAD)" followon' > "$OUT.judge" 2>&1 ;;
esac
missing=$(grep -oE '[A-Za-z0-9_.-]+: command not found' "$OUT.jsonl" | sort | uniq -c | awk '{printf "%s:%s ", $2, $1}')
echo "$task-$arm exit=$rc | $(tail -1 "$OUT.judge") | missing: ${missing:-none}"
