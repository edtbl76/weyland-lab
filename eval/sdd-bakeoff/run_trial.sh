#!/usr/bin/env bash
# Run ONE B86 bake-off trial headless and record it.   usage: run_trial.sh <small|brown|green> <none|aidlc|bmad|openspec|speckit>
# Same for every arm: model, task text (TASK.md), the unattended answer policy, sandbox + permission settings, no MCP,
# a fresh Claude config dir (no user CLAUDE.md, plugins or memory), a turn cap and a wall-clock cap. Only the first
# sentence of the prompt differs: which framework's own entry point to drive.
# Writes results/<task>-<arm>.{jsonl,err,meta}. Refuses to re-run a trial that already has a result.
set -uo pipefail
task="$1"; arm="$2"; suf="${3:-}"   # optional replicate suffix, e.g. -r2
B="${SDD_BAKEOFF_HOME:-/home/edwardmangini/sdd-bakeoff}"   # work dir: trials, results, toolbox (outside the repo)
C="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # harness code: eval/sdd-bakeoff in the repo
D="$B/trials/$task-$arm$suf"
OUT="$B/results/$task-$arm$suf"
MODEL=claude-opus-5-5
MAX_TURNS=250
WALL=3600
[ -d "$D" ] || { echo "no trial dir $D"; exit 2; }
[ -e "$OUT.jsonl" ] && { echo "already ran: $OUT.jsonl"; exit 2; }

case "$arm" in
  none)     lead="Complete the task in TASK.md directly, with no spec-driven framework." ;;
  aidlc)    lead="/aidlc Complete the task described in TASK.md using this repository's AI-DLC workflow end to end." ;;
  aidlc211) lead="/aidlc Complete the task described in TASK.md using this repository's AI-DLC workflow end to end." ;;   # same lead: only the version differs
  bmad)     lead="Complete the task in TASK.md using the BMAD Method installed in this repository (the bmad-* skills): start with bmad-help to pick the BMAD workflow that fits this size of change, then follow that workflow end to end." ;;
  openspec) lead="/opsx:propose Complete the task described in TASK.md. After the proposal, continue with the OpenSpec apply step (openspec-apply-change) to implement it, then archive the change (openspec-archive-change)." ;;
  speckit)  lead="/speckit-specify Complete the task described in TASK.md. Then continue through Spec Kit's workflow in order: speckit-plan, speckit-tasks, speckit-implement." ;;
  *) echo "unknown arm $arm"; exit 2 ;;
esac
policy="You are working UNATTENDED: nobody will read or answer you until you finish. Whenever the workflow asks a question or asks for approval, take its recommended default; if it has no default, choose the first option; then continue without waiting. Use only the tools on PATH (see TASK.md). Do not run git commit or git push. Stop when every acceptance criterion in TASK.md is met, or when you are truly blocked. End with a line 'TRIAL DONE' or 'TRIAL BLOCKED: <reason>', then a short summary of what you changed."

REPLY="Yes - take the recommended option."
MAX_REPLIES=25
if [ "$arm" = aidlc211 ]; then
  # AI-DLC 2.11 accepts an answer only in a real human turn (a standing instruction is refused; found 2026-11-02), so
  # this arm gets a click-through human: whenever the run ends without TRIAL DONE, the SAME session is resumed with
  # $REPLY, up to $MAX_REPLIES times, inside the same total wall cap. Every other part of the protocol is unchanged.
  policy="A person is present, but all they will ever do is approve: whenever the workflow asks a question or asks for approval, show it and end your turn, and the person's reply will take the recommended option. Use only the tools on PATH (see TASK.md). Do not run git commit or git push. Stop when every acceptance criterion in TASK.md is met, or when you are truly blocked. End with a line 'TRIAL DONE' or 'TRIAL BLOCKED: <reason>', then a short summary of what you changed."
fi

T="$B/toolbox"
TMP="$B/tmp/$task-$arm$suf"
mkdir -p "$TMP"
start=$(date -u +%FT%TZ)
t0=$(date +%s)
cd "$D" || exit 2
claude_run() {   # claude_run <wall seconds> <claude args...>  → appends to $OUT.jsonl / $OUT.err
  local wall="$1"; shift
  echo '{"type":"bakeoff_process"}' >> "$OUT.jsonl"   # process boundary (counts processes; cost is session-cumulative)
  env -i HOME="$HOME" USER="${USER:-$(id -un)}" LANG=C.UTF-8 TERM=dumb \
    PATH="$T/bin:$T/venv/bin:/usr/local/bin:/usr/bin:/bin" \
    CLAUDE_CONFIG_DIR="$B/claude-config" TMPDIR="$TMP" \
    npm_config_cache="$TMP/npm" PIP_CACHE_DIR="$TMP/pip" UV_CACHE_DIR="$TMP/uv" XDG_CACHE_HOME="$TMP/xdg" \
    timeout "$wall" "${CLAUDE_BIN:-/home/edwardmangini/.local/bin/claude}" "$@" \
      --model "$MODEL" --max-turns "$MAX_TURNS" \
      --settings "$C/sandbox-settings.json" --strict-mcp-config --mcp-config "$C/no-mcp.json" \
      --permission-mode dontAsk --allowedTools "Read,Edit,Write,Bash,Glob,Grep,Skill,Task,TodoWrite" --permission-prompts none \
      --output-format stream-json --verbose >> "$OUT.jsonl" 2>> "$OUT.err"
}
last_result() {  # the final text of the most recent result event
  python3 -I -c 'import json,sys
r=[e for e in (json.loads(l) for l in open(sys.argv[1]) if l.startswith("{")) if e.get("type")=="result"]
print((r[-1].get("result") or "") if r else "")' "$OUT.jsonl"
}
claude_run "$WALL" -p "$lead $policy"
rc=$?
replies=0
if [ "$arm" = aidlc211 ]; then
  sid=$(python3 -I -c 'import json,sys
print(next((e.get("session_id") for e in (json.loads(l) for l in open(sys.argv[1]) if l.startswith("{")) if e.get("session_id")), ""))' "$OUT.jsonl")
  # stop on a final status: TRIAL DONE, or TRIAL BLOCKED that is not just a gate question ("Reply with ..."), or a
  # reply that changed nothing (same final text twice). Found 2026-11-02: green-aidlc211-r3 said TRIAL BLOCKED at
  # reply 10 and was answered 15 more times for nothing.
  prev=""
  while [ -n "$sid" ] && [ "$replies" -lt "$MAX_REPLIES" ]; do
    cur=$(last_result)
    printf '%s' "$cur" | grep -q "TRIAL DONE" && break
    printf '%s' "$cur" | grep -q "TRIAL BLOCKED" && ! printf '%s' "$cur" | grep -q "Reply with" && break
    [ -n "$prev" ] && [ "$cur" = "$prev" ] && break
    prev=$cur
    left=$((WALL - ($(date +%s) - t0)))
    [ "$left" -le 60 ] && break
    replies=$((replies + 1))
    claude_run "$left" -p "$REPLY" --resume "$sid"
    rc=$?
  done
fi
end=$(date -u +%FT%TZ)
{
  echo "task=$task arm=$arm model=$MODEL max_turns=$MAX_TURNS wall_cap_s=$WALL"
  echo "start=$start end=$end exit=$rc"
  echo "human_replies=$replies"
  echo "files_changed=$(git -C "$D" status --porcelain | wc -l)"
  git -C "$D" status --porcelain | head -60
} > "$OUT.meta"
echo "$task-$arm$suf exit=$rc ($(grep files_changed "$OUT.meta"))"
