#!/usr/bin/env bats
# Tests for check-repo-coverage.sh (B138). Exercises the DECISIONS: enforced-lane parity passes, an enforced
# lane that drifts (missing OR unexpected repo) fails, a pending lane's gap does NOT fail, and the guard fails
# CLOSED on a missing SoT or an unparseable lane config. All paths are fixture-overridden via the guard's env
# seams so no test touches the real repos.yaml. Each failure case is mutation-verified — the mutation is what
# flips the outcome, so a green test proves the check, not the fixture.

setup() {
  GUARD="${BATS_TEST_DIRNAME}/../check-repo-coverage.sh"
  TMP="$(mktemp -d)"
  export REPOS_YAML="$TMP/repos.yaml"
  export PR_STALENESS_FILE="$TMP/pr.yaml"
  export PORT_INTEGRATIONS_FILE="$TMP/port.tf"
  export TOFU_GITHUB_DIR="$TMP/github"; mkdir -p "$TOFU_GITHUB_DIR"
  export SCAN_SUITE_FILE="$TMP/scan-suite.yaml"
  export BACKUP_CONF_FILE="$TMP/backup.conf"
  cat > "$REPOS_YAML" <<'EOF'
enforce: [pr, catalog]
repos:
  - name: weyland-lab
    lanes: { pr: true, catalog: true }
  - name: freejack
    lanes: { pr: true, catalog: true }
EOF
  printf '    REPOS="${PR_REPOS:-edtbl76/weyland-lab edtbl76/freejack}"\n' > "$PR_STALENESS_FILE"
  printf '"query" = ".name | IN(\\"weyland-lab\\", \\"freejack\\")"\n' > "$PORT_INTEGRATIONS_FILE"
  : > "$SCAN_SUITE_FILE"; : > "$BACKUP_CONF_FILE"
}
teardown() { rm -rf "$TMP"; }

@test "enforced lanes in parity -> exit 0" {
  run bash "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"pr"*"parity"* ]]
  [[ "$output" == *"catalog"*"parity"* ]]
}

@test "enforced lane MISSING a repo -> exit 1 (mutation: drop freejack from pr)" {
  printf '    REPOS="${PR_REPOS:-edtbl76/weyland-lab}"\n' > "$PR_STALENESS_FILE"
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"missing: freejack"* ]]
}

@test "enforced lane with an UNEXPECTED repo -> exit 1 (mutation: add off-SoT repo to pr)" {
  printf '    REPOS="${PR_REPOS:-edtbl76/weyland-lab edtbl76/freejack edtbl76/midi_real_book}"\n' > "$PR_STALENESS_FILE"
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"unexpected: midi_real_book"* ]]
}

@test "a PENDING lane gap does NOT fail CI" {
  cat > "$REPOS_YAML" <<'EOF'
enforce: [pr]
repos:
  - name: weyland-lab
    lanes: { pr: true, scan: true }
EOF
  printf '    REPOS="${PR_REPOS:-edtbl76/weyland-lab}"\n' > "$PR_STALENESS_FILE"
  run bash "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"scan"*"missing: weyland-lab"* ]]
}

@test "backup matched by backup_path not name (the freejack/Education case) -> exit 0" {
  cat > "$REPOS_YAML" <<'EOF'
enforce: [backup]
repos:
  - name: freejack
    backup_path: ~/Documents/Education
    lanes: { backup: true }
EOF
  printf '~/Documents/Education\n' > "$BACKUP_CONF_FILE"
  run bash "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"backup"*"parity"* ]]
}

@test "backup enforced: a repo whose backup_path is absent -> exit 1" {
  cat > "$REPOS_YAML" <<'EOF'
enforce: [backup]
repos:
  - name: freejack
    backup_path: ~/Documents/Education
    lanes: { backup: true }
EOF
  : > "$BACKUP_CONF_FILE"
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"missing: freejack"* ]]
}

@test "backup enforced: an orphan allow-list path not claimed by any repo -> exit 1" {
  cat > "$REPOS_YAML" <<'EOF'
enforce: [backup]
repos:
  - name: freejack
    backup_path: ~/Documents/Education
    lanes: { backup: true }
EOF
  printf '~/Documents/Education\n~/some/orphan/dir\n' > "$BACKUP_CONF_FILE"
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"orphan"* ]]
}

@test "scan lane reads SCAN_REPOS from the scan-suite manifest -> parity, exit 0" {
  cat > "$REPOS_YAML" <<'EOF'
enforce: [scan]
repos:
  - name: weyland-lab
    lanes: { scan: true }
  - name: freejack
    lanes: { scan: true }
EOF
  printf '                - name: SCAN_REPOS\n                  value: "weyland-lab freejack"\n' > "$SCAN_SUITE_FILE"
  run bash "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"scan"*"parity"* ]]
}

@test "scan enforced: a scan:true repo missing from SCAN_REPOS -> exit 1" {
  cat > "$REPOS_YAML" <<'EOF'
enforce: [scan]
repos:
  - name: weyland-lab
    lanes: { scan: true }
  - name: freejack
    lanes: { scan: true }
EOF
  printf '                - name: SCAN_REPOS\n                  value: "weyland-lab"\n' > "$SCAN_SUITE_FILE"
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"missing: freejack"* ]]
}

@test "fail-closed: missing SoT -> exit 2" {
  rm -f "$REPOS_YAML"
  run bash "$GUARD"
  [ "$status" -eq 2 ]
  [[ "$output" == *"guard broken"* ]]
}

@test "fail-closed: unparseable pr config -> exit 2" {
  printf 'no repos line here\n' > "$PR_STALENESS_FILE"
  run bash "$GUARD"
  [ "$status" -eq 2 ]
  [[ "$output" == *"guard broken"* ]]
}
