#!/usr/bin/env bats
# check-tofu-fmt.sh — every tracked OpenTofu directory must pass `tofu fmt -check`.
#
# Found 2026-09-24: 7 files across tofu/github, tofu/port and tofu/proxmox had drifted from canonical format and
# nothing in CI would ever have said so. The stubbed `tofu` below answers with the REAL contract, observed on
# OpenTofu 1.12.5 before writing these: exit 0 = formatted (silent), 3 = needs formatting (prints file names),
# 2 = the files do not parse (prints an Error block).

setup() {
  load helper
  setup_stubs
  GUARD="$REPO_ROOT/scripts/check-tofu-fmt.sh"
  D1="$STUB_DIR/tofu-a"; D2="$STUB_DIR/tofu-b"
  mkdir -p "$D1" "$D2"
  export TOFU_DIRS="$D1 $D2"
}

teardown() {
  teardown_stubs
}

@test "every directory formatted -> exit 0, and it says how many it checked" {
  stub tofu 0 ''
  run bash "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"2 OpenTofu director"* ]]
  [ "$(calls_to tofu | grep -c 'fmt -check')" -eq 2 ]
}

@test "a directory needing formatting -> exit 1, names the file and the fix" {
  stub_dispatch tofu
  stub_case tofu "tofu-a" 3 'main.tf'
  stub_case tofu "tofu-b" 0 ''
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"tofu-a"* ]]
  [[ "$output" == *"main.tf"* ]]
  [[ "$output" == *"tofu fmt"* ]]
}

@test "a parse error is exit 2 (guard broken), NOT reported as a formatting finding" {
  stub tofu 2 'Error: Missing expression'
  run bash "$GUARD"
  [ "$status" -eq 2 ]
  [[ "$output" == *"Missing expression"* ]]
}

@test "tofu not installed -> exit 2, never a pass" {
  PATH="$STUB_DIR:/usr/bin:/bin" run bash -c 'command -v tofu >/dev/null && echo HAS_TOFU; bash "$0"' "$GUARD"
  [[ "$output" != *"HAS_TOFU"* ]] || skip "a real tofu is on /usr/bin; cannot simulate its absence here"
  [ "$status" -eq 2 ]
  [[ "$output" == *"tofu"*"not found"* ]]
}

@test "ZERO directories to check is exit 2 — checking nothing is not a pass" {
  stub tofu 0 ''
  TOFU_DIRS=" " run bash "$GUARD"
  [ "$status" -eq 2 ]
  [[ "$output" == *"no OpenTofu"* ]]
}

@test "a listed directory that does not exist is exit 2" {
  stub tofu 0 ''
  TOFU_DIRS="$D1 $STUB_DIR/gone" run bash "$GUARD"
  [ "$status" -eq 2 ]
  [[ "$output" == *"gone"* ]]
}

@test "live discovery finds the repo's real tofu directories (every .tf dir under nodes/)" {
  stub tofu 0 ''
  unset TOFU_DIRS
  run bash "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"tofu/github"* ]]
  [[ "$output" == *"tofu/port"* ]]
}
