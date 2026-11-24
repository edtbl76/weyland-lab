#!/usr/bin/env bats
# nodes/rogueone/ufw/rogueone-ufw.sh (B211, 2026-10-22) — the firewall rules for rogueone's no-auth or front-door ports
# live in git and can be checked. `--check` reads `ufw status numbered` (root only; UFW_STATUS_FILE is the test seam)
# and fails when a desired ALLOW is missing, when the port's DENY is missing, or when the DENY sits ABOVE an ALLOW
# (ufw is first-match, so the ALLOW would never fire). Exit 0 in place · 1 drift, named · 2 cannot check (ufw inactive,
# nothing parsed). The fixture is ufw's documented `status numbered` layout; the first live --check confirms it.

setup() {
  S="$BATS_TEST_DIRNAME/../../nodes/rogueone/ufw/rogueone-ufw.sh"
  F="$BATS_TEST_TMPDIR/status"
  export UFW_STATUS_FILE="$F"
}

good() {
  cat > "$F" <<'EOF'
Status: active

     To                         Action      From
     --                         ------      ----
[ 1] 11434/tcp                  ALLOW IN    192.168.1.233
[ 2] 11434/tcp                  ALLOW IN    192.168.1.243
[ 3] 11434/tcp                  ALLOW IN    172.17.0.0/16
[ 4] 8765/tcp                   ALLOW IN    192.168.1.233
[ 5] 8765/tcp                   ALLOW IN    192.168.1.243
[ 6] 8766/tcp                   ALLOW IN    192.168.1.233
[ 7] 8766/tcp                   ALLOW IN    192.168.1.243
[ 8] 11434/tcp                  DENY IN     Anywhere
[ 9] 8765/tcp                   DENY IN     Anywhere
[10] 8766/tcp                   DENY IN     Anywhere
[11] 11434/tcp (v6)             DENY IN     Anywhere (v6)
[12] 8765/tcp (v6)              DENY IN     Anywhere (v6)
[13] 8766/tcp (v6)              DENY IN     Anywhere (v6)
EOF
}

@test "every rule in place is exit 0, counted" {
  good
  run bash "$S" --check
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [[ "$output" == *"OK — 3 port(s), 7 allow rule(s) and their denies in place"* ]] || { echo "$output"; return 1; }
}

@test "the person-layer memory port (B256) is closed to the LAN: a missing 8766 deny is drift, named" {
  good
  sed -i '/8766\/tcp  *DENY IN  *Anywhere$/d' "$F"
  run bash "$S" --check
  [ "$status" -eq 1 ] || { echo "$output"; return 1; }
  [[ "$output" == *"MISSING: deny 8766/tcp"* ]] || { echo "$output"; return 1; }
}

@test "a missing allow is drift, named" {
  good
  sed -i '/172.17.0.0\/16/d' "$F"
  run bash "$S" --check
  [ "$status" -eq 1 ] || { echo "$output"; return 1; }
  [[ "$output" == *"MISSING: allow 11434/tcp from 172.17.0.0/16"* ]] || { echo "$output"; return 1; }
}

@test "a missing deny is drift, named (the port is open to the LAN)" {
  good
  sed -i '/8765\/tcp  *DENY IN  *Anywhere$/d' "$F"
  run bash "$S" --check
  [ "$status" -eq 1 ] || { echo "$output"; return 1; }
  [[ "$output" == *"MISSING: deny 8765/tcp"* ]] || { echo "$output"; return 1; }
}

@test "a deny above an allow is drift (first match wins, so the allow never fires)" {
  cat > "$F" <<'EOF'
Status: active

     To                         Action      From
     --                         ------      ----
[ 1] 11434/tcp                  DENY IN     Anywhere
[ 2] 11434/tcp                  ALLOW IN    192.168.1.243
[ 3] 11434/tcp                  ALLOW IN    172.17.0.0/16
[ 4] 8765/tcp                   ALLOW IN    192.168.1.243
[ 5] 8765/tcp                   DENY IN     Anywhere
EOF
  run bash "$S" --check
  [ "$status" -eq 1 ] || { echo "$output"; return 1; }
  [[ "$output" == *"ORDER: 11434/tcp deny (rule 1) is above allow from 192.168.1.243 (rule 2)"* ]] || { echo "$output"; return 1; }
}

@test "an inactive firewall is exit 2, never a pass" {
  printf 'Status: inactive\n' > "$F"
  run bash "$S" --check
  [ "$status" -eq 2 ] || { echo "$output"; return 1; }
  [[ "$output" == *"CANNOT CHECK: ufw is not active"* ]] || { echo "$output"; return 1; }
}

@test "output it cannot parse is exit 2, never a pass" {
  printf 'Status: active\n\nsomething else entirely\n' > "$F"
  run bash "$S" --check
  [ "$status" -eq 2 ] || { echo "$output"; return 1; }
  [[ "$output" == *"CANNOT CHECK: no numbered rule parsed"* ]] || { echo "$output"; return 1; }
}

@test "--apply on an EMPTY rule set uses plain allow (ufw rejects insert 1 with no rules), then the denies" {
  printf 'Status: active\n' > "$F"
  run env UFW_DRY_RUN=1 bash "$S" --apply
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [ "$(echo "$output" | head -1)" = "ufw allow from 192.168.1.233 to any port 11434 proto tcp" ] || { echo "$output"; return 1; }
  if echo "$output" | grep -q 'insert'; then echo "insert used on an empty rule set"; return 1; fi
  [ "$(echo "$output" | grep -n 'deny 11434/tcp' | cut -d: -f1)" -gt "$(echo "$output" | grep -n '172.17.0.0/16' | cut -d: -f1)" ]
}

@test "--apply on a LIVE rule set inserts every allow at the top, above the existing denies (first match wins)" {
  # 2026-11-16: a plain `ufw allow` APPENDS, so an allow added after the port's DENY never fires. The live
  # firewall already has its denies, so adding timberback (.233) must insert, not append.
  good
  run env UFW_DRY_RUN=1 bash "$S" --apply
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [[ "$output" == *"ufw insert 1 allow from 192.168.1.233 to any port 11434 proto tcp"* ]] || { echo "$output"; return 1; }
  if echo "$output" | grep -E '^ufw allow '; then echo "an allow was appended"; return 1; fi
}

@test "timberback's allow on 11434 is required: missing is drift, named (litellm calls Ollama from timberback)" {
  good
  sed -i '/11434\/tcp  *ALLOW IN    192.168.1.233/d' "$F"
  run bash "$S" --check
  [ "$status" -eq 1 ]
  [[ "$output" == *"MISSING: allow 11434/tcp from 192.168.1.233"* ]] || { echo "$output"; return 1; }
}

@test "timberback's allow on 8765 is required: missing is drift, named (the memory MCP gateway may run on timberback)" {
  # 2026-11-17: the onboarding taint was lifted, so any unpinned pod — the gateway that reads Basic Memory — can land
  # on timberback and reach rogueone from 192.168.1.233.
  good
  sed -i '/8765\/tcp  *ALLOW IN    192.168.1.233/d' "$F"
  run bash "$S" --check
  [ "$status" -eq 1 ]
  [[ "$output" == *"MISSING: allow 8765/tcp from 192.168.1.233"* ]] || { echo "$output"; return 1; }
}

@test "no mode is a usage error, exit 2" {
  run bash "$S"
  [ "$status" -eq 2 ] || { echo "$output"; return 1; }
}
