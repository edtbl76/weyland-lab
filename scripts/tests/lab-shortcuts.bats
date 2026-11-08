#!/usr/bin/env bats
#
# lab-shortcuts.sh (B187 follow-on) — the interactive shortcuts: lab-commands, lab-ask, vault, vault-rm.
# The decisions live in tested Python (test_lab_commands.py, test_scratch_vault.py); these tests pin the WIRING:
# what reaches `claude`, that a refusal stops before `rm`, and that usage errors say why. `claude` is stubbed and
# never runs for real.

load helper

setup() {
  setup_stubs
  WORK="$(mktemp -d)"
  export HOME="$WORK/home"
  mkdir -p "$HOME"
  export SCRATCH_VAULTS="$WORK/vaults"
  mkdir -p "$SCRATCH_VAULTS"
  # A claude stub that records its argv and its stdin, so the test can see what lab-ask sent.
  cat >"$STUB_DIR/claude" <<EOF
#!/usr/bin/env bash
printf 'claude %s\n' "\$*" >> "$STUB_LOG"
cat > "$STUB_DIR/.claude.stdin"
echo "stub answer"
EOF
  chmod +x "$STUB_DIR/claude"
  WEYLAND_REPO="$REPO_ROOT"
  export WEYLAND_REPO
  # shellcheck source=/dev/null
  source "$REPO_ROOT/scripts/lab-shortcuts.sh"
}

teardown() {
  teardown_stubs
  rm -rf "$WORK"
}

@test "lab-ask with no question prints usage and never calls claude" {
  run lab-ask
  [ "$status" -eq 2 ]
  [[ "$output" == *"usage: lab-ask"* ]]
  [ "$(grep -c '^claude' "$STUB_LOG")" -eq 0 ]
}

@test "lab-ask sends the question and the runbook roster to claude with no tools" {
  run lab-ask "how do I trigger a CI run"
  [ "$status" -eq 0 ]
  [[ "$output" == *"stub answer"* ]]
  grep -q -- '--tools  --no-session-persistence' "$STUB_LOG"
  grep -q -- '--model sonnet' "$STUB_LOG"
  grep -q 'Question: how do I trigger a CI run' "$STUB_DIR/.claude.stdin"
  grep -q 'woodpecker-cli pipeline create edtbl76/weyland-lab --branch main' "$STUB_DIR/.claude.stdin"
}

@test "lab-commands with a word that matches nothing exits 1 with the reason" {
  run lab-commands zzz-no-such-command-anywhere
  [ "$status" -eq 1 ]
  [[ "$output" == *"no command matches"* ]]
}

@test "lab-commands finds the canonical CI trigger" {
  run lab-commands pipeline create weyland-lab
  [ "$status" -eq 0 ]
  [[ "$output" == *"[any] woodpecker-cli pipeline create edtbl76/weyland-lab --branch main"* ]]
}

@test "vault refuses a B-number topic before touching claude-obsidian or claude" {
  run vault b22-search
  [ "$status" -eq 2 ]
  [[ "$output" == *"looks like a B-number"* ]]
  [ "$(grep -c '^claude' "$STUB_LOG")" -eq 0 ]
  [ -z "$(ls -A "$SCRATCH_VAULTS")" ]
}

@test "vault-rm refuses a folder that is not a scratch vault and deletes nothing" {
  mkdir -p "$SCRATCH_VAULTS/notes"
  echo keep >"$SCRATCH_VAULTS/notes/important.md"
  run vault-rm notes
  [ "$status" -eq 2 ]
  [[ "$output" == *"not a scratch vault"* ]]
  [ -f "$SCRATCH_VAULTS/notes/important.md" ]
}

@test "vault-rm deletes a real scratch vault" {
  mkdir -p "$SCRATCH_VAULTS/metasearch/wiki"
  echo '{}' >"$SCRATCH_VAULTS/metasearch/.claude-obsidian.json"
  run vault-rm metasearch
  [ "$status" -eq 0 ]
  [[ "$output" == *"deleted $SCRATCH_VAULTS/metasearch"* ]]
  [ ! -e "$SCRATCH_VAULTS/metasearch" ]
}
