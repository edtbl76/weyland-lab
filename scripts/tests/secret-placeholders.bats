#!/usr/bin/env bats
# B147 — placeholder detection across the SealedSecrets allow-list.
#
# WHY THIS EXISTS: `weyland/port-creds` held the literal strings `YOUR_ID` / `YOUR_SECRET` for 63 days.
# It was sealed, committed, Argo-applied, `DATA 2`, mounted by a running pod — every signal green — and
# it authenticated to nothing, so the B62 AI-Dev Usage pipeline silently never worked. A placeholder and
# a real credential are byte-indistinguishable from the outside; only decoding and LOOKING catches it.
#
# The hard part is not finding placeholders, it is NOT flagging real config. `clickhouse-users` holds an
# XML document beginning `<clickhouse>`, and a naive `<[a-z-]+>` pattern (written for `<your-token>`)
# matched it on the first pass. A guard that cries wolf on a legitimate secret gets muted, and then it
# is worth nothing — the same argument this repo keeps making about permanently-lit alerts.

setup() {
  load helper
  setup_stubs
  GUARD="$REPO_ROOT/scripts/check-secret-placeholders.sh"
}

teardown() {
  teardown_stubs
}

lib_source() {
  SECRET_PLACEHOLDER_LIB=1 source "$GUARD"
}

@test "the guard exists" {
  [ -f "$GUARD" ]
}

# --- is_placeholder: the whole decision ---------------------------------------------------------

@test "flags YOUR_ID — the literal value that cost 63 days" {
  lib_source
  run is_placeholder "YOUR_ID"
  [ "$status" -eq 0 ]
}

@test "flags YOUR_SECRET" {
  lib_source
  run is_placeholder "YOUR_SECRET"
  [ "$status" -eq 0 ]
}

@test "flags CHANGEME and its variants" {
  lib_source
  for v in CHANGEME changeme CHANGE_ME change-me; do
    run is_placeholder "$v"
    [ "$status" -eq 0 ]
  done
}

@test "flags an angle-bracket placeholder" {
  lib_source
  run is_placeholder "<your-token-here>"
  [ "$status" -eq 0 ]
}

@test "flags REPLACE_ME / PLACEHOLDER / TODO" {
  lib_source
  for v in REPLACE_ME PLACEHOLDER TODO; do
    run is_placeholder "$v"
    [ "$status" -eq 0 ]
  done
}

@test "flags an EMPTY value — a secret that holds nothing is its own bug" {
  lib_source
  run is_placeholder ""
  [ "$status" -eq 0 ]
}

# --- what it must NOT flag ----------------------------------------------------------------------

@test "does NOT flag a real 64-char credential" {
  lib_source
  run is_placeholder "hZ8kQ2mNpX4vR7tY1wA3sD5fG6hJ9kL0zXcVbNmQwErTyUiOpAsDfGhJkLzXcVbN"
  [ "$status" -ne 0 ]
}

@test "does NOT flag a real 32-char client id" {
  lib_source
  run is_placeholder "aB3dE6gH9jK2mN5pQ8sT1vW4xY7zC0eF"
  [ "$status" -ne 0 ]
}

@test "does NOT flag an XML config document — the clickhouse-users false positive" {
  # This is the case that broke the first version. `<clickhouse>` matched a pattern written for
  # `<your-token>`. A multi-line structured document is config, not a credential.
  lib_source
  run is_placeholder '<clickhouse><users><default><password>real</password></default></users></clickhouse>'
  [ "$status" -ne 0 ]
}

@test "does NOT flag a multi-line config blob" {
  lib_source
  run is_placeholder "$(printf 'line one\nline two\nline three')"
  [ "$status" -ne 0 ]
}

@test "does NOT flag a long value that merely CONTAINS the word test" {
  # `test` alone is a placeholder; a credential that happens to contain it is not.
  lib_source
  run is_placeholder "prod-latest-signing-key-9f3a2b7c8d1e4f5a6b7c8d9e0f1a2b3c"
  [ "$status" -ne 0 ]
}

@test "does NOT flag a PEM private key" {
  lib_source
  run is_placeholder "$(printf -- '-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXktdjEA\n-----END OPENSSH PRIVATE KEY-----')"
  [ "$status" -ne 0 ]
}

# --- allow-list parsing -------------------------------------------------------------------------

@test "reads the allow-list from seal-secrets.sh rather than duplicating it" {
  # Two copies of the list would drift, and the drift would be silent on BOTH sides.
  lib_source
  cat > "$STUB_DIR/seal.sh" <<'SH'
SECRETS=(
  # a comment
  weyland/alpha
  data-mesh/beta   # trailing comment
)
SH
  run allow_list_entries "$STUB_DIR/seal.sh"
  [ "$status" -eq 0 ]
  [[ "$output" == *"weyland/alpha"* ]]
  [[ "$output" == *"data-mesh/beta"* ]]
  [[ "$output" != *"#"* ]]
}

@test "an allow-list it cannot parse is FATAL, not an empty list" {
  # An empty list would mean "checked nothing, found nothing" — a clean pass over zero secrets.
  lib_source
  printf 'no secrets array here\n' > "$STUB_DIR/empty.sh"
  run allow_list_entries "$STUB_DIR/empty.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"SECRETS"* ]]
}

@test "a missing seal script is FATAL" {
  lib_source
  run allow_list_entries "$STUB_DIR/does-not-exist.sh"
  [ "$status" -ne 0 ]
}

# --- end to end, against a snapshot --------------------------------------------------------------

@test "end to end: a clean snapshot passes" {
  cat > "$STUB_DIR/seal.sh" <<'SH'
SECRETS=(
  weyland/good
)
SH
  printf '{"weyland/good":{"token":"aB3dE6gH9jK2mN5pQ8sT1vW4xY7zC0eF"}}' > "$STUB_DIR/snap.json"
  SEAL_SCRIPT="$STUB_DIR/seal.sh" SECRET_SNAPSHOT_JSON="$STUB_DIR/snap.json" run bash "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"OK"* ]]
}

@test "end to end: a placeholder FAILS and names the secret AND the key" {
  cat > "$STUB_DIR/seal.sh" <<'SH'
SECRETS=(
  weyland/port-creds
)
SH
  printf '{"weyland/port-creds":{"PORT_CLIENT_ID":"YOUR_ID","PORT_CLIENT_SECRET":"YOUR_SECRET"}}' > "$STUB_DIR/snap.json"
  SEAL_SCRIPT="$STUB_DIR/seal.sh" SECRET_SNAPSHOT_JSON="$STUB_DIR/snap.json" run bash "$GUARD"
  [ "$status" -ne 0 ]
  [[ "$output" == *"port-creds"* ]]
  [[ "$output" == *"PORT_CLIENT_ID"* ]]
}

@test "end to end: a secret in the allow-list but MISSING from the cluster is FATAL" {
  # Not "nothing to check". A secret we were told to watch that is absent is the failure.
  cat > "$STUB_DIR/seal.sh" <<'SH'
SECRETS=(
  weyland/ghost
)
SH
  printf '{}' > "$STUB_DIR/snap.json"
  SEAL_SCRIPT="$STUB_DIR/seal.sh" SECRET_SNAPSHOT_JSON="$STUB_DIR/snap.json" run bash "$GUARD"
  [ "$status" -ne 0 ]
  [[ "$output" == *"ghost"* ]]
}

@test "end to end: the XML config secret does NOT fail the run" {
  cat > "$STUB_DIR/seal.sh" <<'SH'
SECRETS=(
  data-mesh/clickhouse-users
)
SH
  python3 -c "
import json
json.dump({'data-mesh/clickhouse-users':{'weyland-users.xml':'<clickhouse>\n  <users><default><password>hunter2</password></default></users>\n</clickhouse>'}}, open('$STUB_DIR/snap.json','w'))
"
  SEAL_SCRIPT="$STUB_DIR/seal.sh" SECRET_SNAPSHOT_JSON="$STUB_DIR/snap.json" run bash "$GUARD"
  [ "$status" -eq 0 ]
}
