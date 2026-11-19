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
  # B250: the missing-ADR check reads a backlog; by default a fixture with no post-cutoff verdict, so the format tests
  # above it are about the format alone. The real backlog is checked by "the real ADR log is valid".
  export BACKLOG="$T/backlog.md"
  backlog '- **B100** — **an old spike** — **DONE 2026-10-01 — DON'"'"'T ADOPT** (Low).'
}

# backlog <line>... — a backlog fixture made of these item lines
backlog() {
  printf '%s\n' "# Backlog" "" "$@" >"$BACKLOG"
}

# more_info <adr-file> <text> — add a "## More Information" section naming the decision's sources
more_info() {
  printf '\n## More Information\n\n%s\n' "$2" >>"$T/adr/$1"
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
  unset ADR_DIR BACKLOG
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

# ---- B250 (2026-11-19): a verdict with no ADR fails -------------------------------------------------------------------
# AGENTS.md: a spike that reaches an ADOPT or DON'T ADOPT verdict gets an ADR. Items closed after 2026-11-13 (when B248
# seeded the log) must have an ADR that names their B-number under "## More Information". The verdict is read from the
# item's "DONE <date> — ..." status only, so prose elsewhere never counts. Fixture lines copy real backlog shapes.

@test "a post-cutoff DON'T ADOPT with no ADR fails, naming the item" {
  backlog '- **B900** — **Spike: some tool** — **DONE 2026-11-20 — DON'"'"'T ADOPT** (MEDIUM, Linear EMA-900).'
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"B900"*"DONE 2026-11-20"*"no ADR"* ]]
}

@test "it passes once an ADR names the item under More Information" {
  backlog '- **B900** — **Spike: some tool** — **DONE 2026-11-20 — DON'"'"'T ADOPT** (MEDIUM, Linear EMA-900).'
  more_info 0002-second-decision.md "Spike: [backlog B900](../backlog.md)."
  run bash "$GUARD"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [[ "$output" == *"1 with a verdict"* ]]
}

@test "naming the item anywhere but More Information does not count" {
  backlog '- **B900** — **Spike: some tool** — **DONE 2026-11-20 — DON'"'"'T ADOPT** (MEDIUM).'
  sed -i 's/^Why a decision was needed.$/Why a decision was needed (B900)./' "$T/adr/0002-second-decision.md"
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"B900"* ]]
}

@test "a pre-cutoff verdict with no ADR passes (B248 seeded those)" {
  backlog '- **B901** — **old** — **DONE 2026-11-12 — DON'"'"'T ADOPT** (Low).'
  run bash "$GUARD"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
}

@test "a lowercase past-tense verdict counts (B248 and B247's real wording)" {
  backlog '### B902 — x — **DONE 2026-11-14 — the `adr` plugin; `git-adr` rejected** (Medium).' \
          '- **B903** — y — **DONE 2026-11-15 — adaptive depth adopted; decomposition lost** (MEDIUM).'
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"B902"* && "$output" == *"B903"* ]]
}

@test "WON'T DO and KEPT are verdicts too" {
  backlog '- **B904** — z — **DONE 2026-11-16 — WON'"'"'T DO** (Low).' \
          '- **B905** — w — **DONE 2026-11-17: scratch vault KEPT as a habit** (Low).'
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"B904"* && "$output" == *"B905"* ]]
}

@test "a post-cutoff close with no verdict word needs no ADR" {
  backlog '- **B906** — **build a thing** — **DONE 2026-11-19 (Linear EMA-906)** (Low).'
  run bash "$GUARD"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
}

@test "closed items with no verdict among them are reported, not silent" {
  backlog '- **B906** — **build a thing** — **DONE 2026-11-19 (Linear EMA-906)** (Low).'
  run bash "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"1 closed since 2026-11-13, 0 with a verdict"* ]]
}

@test "verdict prose outside the DONE status does not count" {
  backlog '- **B907** — **build** — **DONE 2026-11-19** (Low). We considered and rejected two designs along the way.'
  run bash "$GUARD"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
}

@test "a missing backlog is exit 2, never a pass" {
  export BACKLOG="$T/no-backlog.md"
  run bash "$GUARD"
  [ "$status" -eq 2 ]
  [[ "$output" == *"backlog"* ]]
}

@test "AGENTS.md and the runbook must state the same ADR trigger" {
  cp "$REPO_ROOT/AGENTS.md" "$T/AGENTS.md"
  sed -i 's/^  - (b) we choose between two or more options.*/  - (b) we pick something./' "$T/AGENTS.md"
  export AGENTS_MD="$T/AGENTS.md"
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"trigger"*"(b)"* ]]
}
