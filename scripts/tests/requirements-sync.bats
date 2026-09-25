#!/usr/bin/env bats
# check-requirements-sync.sh — every exact `==` pin in a requirements.in must equal its requirements.txt pin.
#
# Found 2026-09-25: services/genre-trainer/requirements.in still pinned cryptography 48.0.1 / mlflow 3.14.0 /
# aiohttp 3.14.1 after main had hand-remediated requirements.txt to 50.0.0 / 3.15.1 / 3.14.3. Nothing installs
# the .in (Dockerfiles install .txt), but dependabot treats it as the pip-compile SOURCE — so every re-cut of
# weyland-lab #63 regenerated .txt from the stale pins and re-opened 4 CVEs. Only the Sourcery check stopped it.

setup() {
  GUARD="${BATS_TEST_DIRNAME}/../check-requirements-sync.sh"
  TMP="$(mktemp -d)"
  export REQ_ROOT="$TMP"
  mkdir -p "$TMP/svc-a" "$TMP/svc-b"
  printf 'aiohttp==3.14.3\ncryptography==50.0.0\n' > "$TMP/svc-a/requirements.in"
  printf 'aiohttp==3.14.3\ncryptography==50.0.0\nmultidict==6.7.1\n' > "$TMP/svc-a/requirements.txt"
  printf 'dagster>=1.8\nrequests\n' > "$TMP/svc-b/requirements.in"
  printf 'dagster==1.9.0\nrequests==2.32.0\n' > "$TMP/svc-b/requirements.txt"
}
teardown() { rm -rf "$TMP"; }

@test "every exact .in pin matches its .txt -> exit 0, says how many files" {
  run bash "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"2 requirements.in"* ]]
}

@test "the genre-trainer case: an .in pin BEHIND its .txt -> exit 1, names file, package, both versions" {
  printf 'aiohttp==3.14.3\ncryptography==48.0.1\n' > "$TMP/svc-a/requirements.in"
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"svc-a/requirements.in"* ]]
  [[ "$output" == *"cryptography"* ]]
  [[ "$output" == *"48.0.1"* ]]
  [[ "$output" == *"50.0.0"* ]]
}

@test "names compare the way pip does (case, _ vs -)" {
  printf 'PyYAML==6.0.2\ntyping_extensions==4.15.0\n' > "$TMP/svc-a/requirements.in"
  printf 'pyyaml==6.0.2\ntyping-extensions==4.15.0\n' > "$TMP/svc-a/requirements.txt"
  run bash "$GUARD"
  [ "$status" -eq 0 ]
}

@test "loose .in entries (>=, bare names) are pip-compile's job, not drift" {
  run bash "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" != *"svc-b"*"drift"* ]]
}

@test "comments, extras, env markers and pip-compile hash lines parse" {
  printf 'requests[socks]==2.32.0 ; python_version > "3.8"  # why\n# a comment\n' > "$TMP/svc-a/requirements.in"
  printf 'requests[socks]==2.32.0 \\\n    --hash=sha256:abc\n    # via -r requirements.in\n' > "$TMP/svc-a/requirements.txt"
  run bash "$GUARD"
  [ "$status" -eq 0 ]
}

@test "an exact .in pin MISSING from .txt -> exit 1" {
  printf 'aiohttp==3.14.3\ncryptography==50.0.0\nnewpkg==1.0\n' > "$TMP/svc-a/requirements.in"
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"newpkg"* ]]
}

@test "an .in with no sibling .txt -> exit 2 (cannot judge)" {
  rm "$TMP/svc-b/requirements.txt"
  run bash "$GUARD"
  [ "$status" -eq 2 ]
  [[ "$output" == *"svc-b"* ]]
}

@test "ZERO requirements.in files -> exit 2, checking nothing is not a pass" {
  rm "$TMP/svc-a/requirements.in" "$TMP/svc-b/requirements.in"
  run bash "$GUARD"
  [ "$status" -eq 2 ]
  [[ "$output" == *"no requirements.in"* ]]
}

@test "live: the repo's real services are in sync (default root)" {
  unset REQ_ROOT
  run bash "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"genre-trainer"* ]]
}
