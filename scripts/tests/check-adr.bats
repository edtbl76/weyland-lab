#!/usr/bin/env bats
# B248 — scripts/check-adr.sh, the repo guard for the Architecture Decision Record log (docs/adr/, MADR files written
# with the zircote-plugins/adr Claude Code plugin or by hand from its template).
#
# What it must catch: an ADR missing a required section, a status outside the workflow, a "Superseded by" that points
# at no ADR, gaps or duplicates in the numbering, and an index (README.md) out of step with the files. Exit codes are
# the contract: 0 valid · 1 a real defect · 2 could not run (no log at all is "could not run", never a pass).
# Each test asserts the reason in the output, not just the status.

setup() {
  load helper
  GUARD="$REPO_ROOT/scripts/check-adr.sh"
  T="$(mktemp -d)"
  mkdir -p "$T/adr"
  export ADR_DIR="$T/adr"
  adr 0001 "first-decision" "accepted"
  adr 0002 "second-decision" "accepted"
  index
}

teardown() {
  rm -rf "$T"
}

# adr <number> <slug> <status-line>
adr() {
  cat >"$T/adr/$1-$2.md" <<EOF
# $2

## Status

$3

## Context and Problem Statement

Why a decision was needed.

## Considered Options

* Option A
* Option B

## Decision Outcome

Chosen option: "Option A", because it is the only one that works.

### Consequences

* Good, because it works.
EOF
}

# index — a README.md listing every ADR file currently in the directory
index() {
  {
    echo "# Architecture Decision Records"
    echo
    echo "| ID | Title | Status | Date |"
    echo "|----|-------|--------|------|"
    for f in "$T"/adr/[0-9][0-9][0-9][0-9]-*.md; do
      b="$(basename "$f")"
      echo "| [${b:0:4}](./$b) | ${b:5} | accepted | 2026-11-13 |"
    done
  } >"$T/adr/README.md"
}

@test "the real ADR log is valid" {
  unset ADR_DIR
  run bash "$GUARD"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [[ "$output" == *"adr: "*" ADR(s) valid"* ]]
}

@test "a valid log passes and says how many ADRs it checked" {
  run bash "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"adr: 2 ADR(s) valid"* ]]
}

@test "an ADR missing a required section fails, naming the file and the section" {
  sed -i '/^## Considered Options/,/^\* Option B/d' "$T/adr/0002-second-decision.md"
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"0002-second-decision.md"*"Considered Options"* ]]
}

@test "a status outside the workflow fails" {
  sed -i 's/^accepted$/maybe-later/' "$T/adr/0001-first-decision.md"
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"0001-first-decision.md"*"status"*"maybe-later"* ]]
}

@test "a superseded ADR that links an existing successor passes" {
  sed -i 's#^accepted$#Superseded by [ADR-0002](./0002-second-decision.md)#' "$T/adr/0001-first-decision.md"
  run bash "$GUARD"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
}

@test "Superseded by an ADR that does not exist fails" {
  sed -i 's#^accepted$#Superseded by [ADR-0009](./0009-gone.md)#' "$T/adr/0001-first-decision.md"
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"0001-first-decision.md"*"ADR-0009"* ]]
}

@test "a gap in the numbering fails" {
  mv "$T/adr/0002-second-decision.md" "$T/adr/0003-second-decision.md"
  index
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"numbering"*"0002"* ]]
}

@test "two ADRs with the same number fail" {
  adr 0002 "another-second" "accepted"
  index
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"duplicate"*"0002"* ]]
}

@test "an ADR missing from the index fails" {
  adr 0003 "third-decision" "proposed"
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"README.md"*"0003-third-decision.md"* ]]
}

@test "an index row pointing at no file fails" {
  echo "| [0004](./0004-ghost.md) | ghost | accepted | 2026-11-13 |" >>"$T/adr/README.md"
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"README.md"*"0004-ghost.md"* ]]
}

@test "no ADR directory is exit 2 (could not run), never a pass" {
  export ADR_DIR="$T/missing"
  run bash "$GUARD"
  [ "$status" -eq 2 ]
  [[ "$output" == *"no ADR directory"* ]]
}

@test "a directory with no ADRs is exit 2, never a pass" {
  rm "$T"/adr/0*.md
  run bash "$GUARD"
  [ "$status" -eq 2 ]
  [[ "$output" == *"no ADRs"* ]]
}
