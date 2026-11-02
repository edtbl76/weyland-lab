#!/usr/bin/env bash
# Spec-as-oracle, step 3: one READ-ONLY review of trials4/<task>-<arm>-<variant>. Identical prompt, model, caps and
# sandbox for every case; tools Read/Glob/Grep only (no shell: the reviewer can neither run the tests nor diff git).
#   usage: run_review.sh <task> <arm> <variant> <target file>  → results/oracle/<task>-<arm>-<variant>.jsonl
set -uo pipefail
task="$1"; arm="$2"; variant="$3"; tgt="$4"
B="${SDD_BAKEOFF_HOME:-/home/edwardmangini/sdd-bakeoff}"   # work dir: trials, results, toolbox (outside the repo)
C="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # harness code: eval/sdd-bakeoff in the repo
# ORACLE=2 → v2 (intent defects): repos in trials5, results in results/oracle2, and the prompt says the tests may have
# been changed to match (true for every v2 defect, so passing-looking tests are no evidence). Identical for docs/nodocs.
if [ "${ORACLE:-1}" = 2 ]; then TD=trials5; RD=results/oracle2; else TD=trials4; RD=results/oracle; fi
D="$B/$TD/$task-$arm-$variant"
OUT="$B/$RD/$task-$arm-$variant"
[ -e "$OUT.jsonl" ] && { echo "already ran $OUT"; exit 0; }
prompt="This repository's file $tgt contains ONE deliberately introduced defect: a small code change that makes it behave differently from what it is meant to do. Find it by reading only (you cannot run anything). Use whatever in the repository tells you what the code is meant to do. Do not modify any file. End your answer with a final line exactly in this form: DEFECT LINE: <the line number in $tgt>"
[ "${ORACLE:-1}" = 2 ] && prompt="This repository's file $tgt contains ONE deliberately introduced defect: a small change that makes it behave differently from what it is meant to do. Its tests may have been changed to agree with the defect, so code and tests agreeing proves nothing. Find it by reading only (you cannot run anything). Use whatever in the repository tells you what the code is meant to do. Do not modify any file. End your answer with a final line exactly in this form: DEFECT LINE: <the line number in $tgt>"
TMP="$B/tmp-oracle${ORACLE:-1}/$task-$arm-$variant"; mkdir -p "$TMP"
cd "$D" || exit 2
env -i HOME="$HOME" USER="${USER:-$(id -un)}" LANG=C.UTF-8 TERM=dumb PATH="/usr/local/bin:/usr/bin:/bin" \
  CLAUDE_CONFIG_DIR="$B/claude-config" TMPDIR="$TMP" \
  timeout 900 /home/edwardmangini/.local/bin/claude -p "$prompt" \
    --model claude-opus-5-5 --max-turns 60 \
    --settings "$C/sandbox-settings.json" --strict-mcp-config --mcp-config "$C/no-mcp.json" \
    --permission-mode dontAsk --allowedTools "Read,Glob,Grep" --disallowedTools "Bash,Edit,Write,Task" --permission-prompts none \
    --output-format stream-json --verbose > "$OUT.jsonl" 2> "$OUT.err"
echo "$task-$arm-$variant exit=$?"
