#!/usr/bin/env bats
# B250 (2026-11-19) — .claude/hooks/adr-verdict-reminder.py, a Claude Code PostToolUse hook on Edit|MultiEdit|Write.
# When an edit ADDS a decision verdict to docs/backlog.md or docs/concepts/*, it returns additionalContext reminding the
# agent that AGENTS.md wants an ADR. It never blocks, calls no model, starts no agent; every failure is silent (exit 0,
# no output), because scripts/check-adr.sh still catches the missing ADR in CI. What counts as a verdict comes from
# scripts/lib/adr_verdicts.py, shared with that guard.
# Fixtures are the hook-input JSON Claude Code sends: {tool_name, tool_input: {file_path, old_string, new_string | edits
# | content}}.

setup() {
  load helper
  HOOK="$REPO_ROOT/.claude/hooks/adr-verdict-reminder.py"
  T="$(mktemp -d)"
  # a throwaway project: a git repo whose HEAD backlog holds ONE verdict
  mkdir -p "$T/proj/docs/concepts"
  printf '# Backlog\n\n- **B1** — old — **DONE 2026-10-01 — DON'"'"'T ADOPT** (Low).\n' >"$T/proj/docs/backlog.md"
  git -C "$T/proj" init -q && git -C "$T/proj" -c user.email=t@t -c user.name=t add -A \
    && git -C "$T/proj" -c user.email=t@t -c user.name=t commit -qm init
  export CLAUDE_PROJECT_DIR="$T/proj"
  BACKLOG="$T/proj/docs/backlog.md"
}

teardown() {
  rm -rf "$T"
}

# edit <file> <old> <new> — the hook input for an Edit
edit() {
  python3 -c 'import json,sys; print(json.dumps({"tool_name": "Edit", "tool_input": {"file_path": sys.argv[1], "old_string": sys.argv[2], "new_string": sys.argv[3]}}))' "$@"
}

hook() {
  run bash -c "python3 '$HOOK' <<<'$(printf '%s' "$1" | sed "s/'/'\\\\''/g")'"
}

@test "an Edit that adds DON'T ADOPT to the backlog reminds about the ADR" {
  hook "$(edit "$BACKLOG" "- **B2** — spike — open" "- **B2** — spike — **DONE 2026-11-20 — DON'T ADOPT** (Low).")"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"additionalContext"'* ]]
  [[ "$output" == *"ADR"* && "$output" == *"/adr:new"* && "$output" == *"/adr:supersede"* ]]
  python3 -c 'import json,sys; d=json.loads(sys.argv[1]); assert d["hookSpecificOutput"]["hookEventName"] == "PostToolUse"' "$output"
}

@test "an Edit inside an item that already has its verdict stays silent" {
  hook "$(edit "$BACKLOG" "**DONE 2026-10-01 — DON'T ADOPT** (Low)." "**DONE 2026-10-01 — DON'T ADOPT** (Low, typo fixed).")"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "an edit to any other file stays silent, even with a verdict" {
  hook "$(edit "$T/proj/README.md" "x" "**DONE 2026-11-20 — DON'T ADOPT**")"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "an Edit adding plain text with no verdict stays silent" {
  hook "$(edit "$BACKLOG" "(Low)." "(Low). Some more notes about the work.")"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "verdict words in prose outside a DONE status stay silent" {
  hook "$(edit "$BACKLOG" "(Low)." "(Low). We rejected two designs on the way.")"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "a MultiEdit where one edit adds a verdict reminds" {
  input="$(python3 -c 'import json,sys; print(json.dumps({"tool_name": "MultiEdit", "tool_input": {"file_path": sys.argv[1], "edits": [{"old_string": "a", "new_string": "b"}, {"old_string": "open", "new_string": "**DONE 2026-11-21 — WON'"'"'T DO**"}]}}))' "$BACKLOG")"
  hook "$input"
  [ "$status" -eq 0 ]
  [[ "$output" == *"additionalContext"* ]]
}

@test "a Write fires only when the verdict count rises against git HEAD" {
  same="$(cat "$BACKLOG"; printf -- '- **B3** — more text, no verdict.\n')"
  hook "$(python3 -c 'import json,sys; print(json.dumps({"tool_name": "Write", "tool_input": {"file_path": sys.argv[1], "content": sys.argv[2]}}))' "$BACKLOG" "$same")"
  [ "$status" -eq 0 ]
  [ -z "$output" ]                                   # the file already holds a verdict: that is not an addition
  more="$(cat "$BACKLOG"; printf -- '- **B4** — x — **DONE 2026-11-22 — adopted**.\n')"
  hook "$(python3 -c 'import json,sys; print(json.dumps({"tool_name": "Write", "tool_input": {"file_path": sys.argv[1], "content": sys.argv[2]}}))' "$BACKLOG" "$more")"
  [ "$status" -eq 0 ]
  [[ "$output" == *"additionalContext"* ]]
}

@test "an Edit adding a verdict to a concept doc reminds" {
  hook "$(edit "$T/proj/docs/concepts/tool.md" "| Tool X | pending |" "| Tool X | DON'T ADOPT |")"
  [ "$status" -eq 0 ]
  [[ "$output" == *"additionalContext"* ]]
}

@test "malformed hook input exits 0 with no output (never blocks)" {
  hook "{not json"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "a Write with git unavailable exits 0 with no output" {
  more="$(cat "$BACKLOG"; printf -- '- **B4** — x — **DONE 2026-11-22 — DON'"'"'T ADOPT**.\n')"
  input="$(python3 -c 'import json,sys; print(json.dumps({"tool_name": "Write", "tool_input": {"file_path": sys.argv[1], "content": sys.argv[2]}}))' "$BACKLOG" "$more")"
  mkdir -p "$T/nogit"; ln -s "$(command -v python3)" "$T/nogit/python3"
  run env PATH="$T/nogit" python3 "$HOOK" <<<"$input"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "the hook and check-adr.sh take the verdict pattern from the one shared module" {
  grep -q "import adr_verdicts" "$HOOK"
  grep -q "import adr_verdicts" "$REPO_ROOT/scripts/check-adr.sh"
  # neither defines its own marker words: those live only in scripts/lib/adr_verdicts.py
  ! grep -qi "won\['’\]t do\|don\['’\]t adopt" "$HOOK"
  ! grep -qi "won\['’\]t do\|don\['’\]t adopt" "$REPO_ROOT/scripts/check-adr.sh"
  grep -qi "don\['’\]t adopt" "$REPO_ROOT/scripts/lib/adr_verdicts.py"
}

@test "settings.json wires the hook on Edit|MultiEdit|Write (an AI-DLC reinstall that copies its own settings.json drops it)" {
  python3 - "$REPO_ROOT/.claude/settings.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
hits = [e for e in d["hooks"]["PostToolUse"]
        if e.get("matcher") == "Edit|MultiEdit|Write"
        and any("adr-verdict-reminder.py" in h.get("command", "") for h in e.get("hooks", []))]
assert len(hits) == 1, "settings.json does not wire .claude/hooks/adr-verdict-reminder.py (see docs/runbooks/adr.md)"
PY
}
