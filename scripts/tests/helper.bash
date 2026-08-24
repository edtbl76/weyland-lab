# Shared setup for the bats suites under scripts/tests/. Source it from a test file's `setup()`:
#
#   load helper
#
# WHY STUBS AND NOT MOCKS: the scripts under test are orchestrators — their whole job is deciding
# what to do with what `git`, `gh`, `woodpecker-cli`, `argocd` and `kubectl` say. A test must never
# let one of those run for real (a stray `gh pr merge` merges a real PR; a stray `argocd app sync`
# touches the live cluster), so every test prepends a temp dir of fake executables to PATH. The
# assertion is always on the DECISION the script reaches, never on the canned output itself.

# Resolve the repo root from this file, not from the caller's cwd, so a test can be run from
# anywhere. Two levels up: scripts/tests/helper.bash -> scripts/tests -> scripts -> repo root.
WEYLAND_TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$WEYLAND_TEST_DIR/../.." && pwd)"
FIXTURES="$WEYLAND_TEST_DIR/fixtures"
export WEYLAND_TEST_DIR REPO_ROOT FIXTURES

# A fixed clock. Age-threshold tests compute against this instead of `date` at runtime, so a test
# that passes today still passes next month. 2026-08-22T12:00:00Z.
export NOW_EPOCH=1787313600

# setup_stubs — create the temp stub dir and put it FIRST on PATH.
# Call from setup(). teardown_stubs() removes it.
setup_stubs() {
  STUB_DIR="$(mktemp -d)"
  STUB_LOG="$STUB_DIR/.calls"
  : >"$STUB_LOG"
  export STUB_DIR STUB_LOG
  PATH="$STUB_DIR:$PATH"
  export PATH
}

teardown_stubs() {
  [ -n "${STUB_DIR:-}" ] && [ -d "$STUB_DIR" ] && rm -rf "$STUB_DIR"
  return 0
}

# stub <name> <exit-code> [stdout...]
#
# Creates $STUB_DIR/<name> as an executable that appends its full argv to $STUB_LOG, prints the
# given stdout, and exits with the given code. Every invocation behaves identically — when a test
# needs a command to answer differently on successive calls, use stub_seq instead.
stub() {
  local name="$1" code="$2"
  shift 2
  local out="$*"
  {
    echo '#!/usr/bin/env bash'
    printf 'printf "%%s %%s\\n" "%s" "$*" >> "%s"\n' "$name" "$STUB_LOG"
    printf 'cat <<'"'"'STUB_EOF'"'"'\n%s\nSTUB_EOF\n' "$out"
    printf 'exit %s\n' "$code"
  } >"$STUB_DIR/$name"
  chmod +x "$STUB_DIR/$name"
}

# stub_seq <name> — start a stub whose behaviour is driven by a response file, one response per
# invocation. Feed it with stub_seq_add; after the list is exhausted the last response repeats.
#
#   stub_seq woodpecker-cli
#   stub_seq_add woodpecker-cli 0 'status: running'
#   stub_seq_add woodpecker-cli 0 'status: success'
#
# This is what makes "poll until the pipeline finishes" testable without a sleep.
stub_seq() {
  local name="$1"
  local resp="$STUB_DIR/.$name.responses"
  : >"$resp"
  : >"$STUB_DIR/.$name.n"
  {
    echo '#!/usr/bin/env bash'
    printf 'printf "%%s %%s\\n" "%s" "$*" >> "%s"\n' "$name" "$STUB_LOG"
    printf 'resp="%s"\n' "$resp"
    printf 'ctr="%s"\n' "$STUB_DIR/.$name.n"
    cat <<'BODY'
n=$(( $(wc -l < "$ctr") + 1 ))
echo x >> "$ctr"
total=$(grep -c '^' "$resp")
[ "$n" -gt "$total" ] && n="$total"
line=$(sed -n "${n}p" "$resp")
code="${line%%|*}"
printf '%s\n' "${line#*|}"
exit "$code"
BODY
  } >"$STUB_DIR/$name"
  chmod +x "$STUB_DIR/$name"
}

# stub_seq_add <name> <exit-code> <stdout-one-line>
stub_seq_add() {
  local name="$1" code="$2"
  shift 2
  printf '%s|%s\n' "$code" "$*" >>"$STUB_DIR/.$name.responses"
}

# stub_dispatch <name> — a stub that answers differently depending on its argv. Needed because one
# binary wears several hats in this loop: `gh pr list`, `gh pr diff`, `gh pr merge` and `gh pr close`
# are four different answers from one command. Register the hats with stub_case, first match wins.
#
#   stub_dispatch gh
#   stub_case gh 'pr list'  0 "$(cat "$FIXTURES/open-prs.json")"
#   stub_case gh 'pr merge' 0 'merged'
#
# An unmatched invocation exits 0 with no output — a stub should not fail a test for a call the test
# did not care about.
stub_dispatch() {
  local name="$1"
  : >"$STUB_DIR/.$name.cases"
  : >"$STUB_DIR/.$name.ncase"
  {
    echo '#!/usr/bin/env bash'
    printf 'printf "%%s %%s\\n" "%s" "$*" >> "%s"\n' "$name" "$STUB_LOG"
    printf 'cases="%s"\n' "$STUB_DIR/.$name.cases"
    cat <<'BODY'
argv="$*"
while IFS='|' read -r pattern code payload; do
  [ -n "$pattern" ] || continue
  case "$argv" in
    *"$pattern"*)
      [ -f "$payload" ] && cat "$payload"
      exit "$code"
      ;;
  esac
done < "$cases"
exit 0
BODY
  } >"$STUB_DIR/$name"
  chmod +x "$STUB_DIR/$name"
}

# stub_case <name> <argv-substring> <exit-code> <stdout>
stub_case() {
  local name="$1" pattern="$2" code="$3"
  shift 3
  local n
  n="$(( $(wc -l <"$STUB_DIR/.$name.ncase") + 1 ))"
  echo x >>"$STUB_DIR/.$name.ncase"
  local payload="$STUB_DIR/.$name.$n.out"
  printf '%s\n' "$*" >"$payload"
  printf '%s|%s|%s\n' "$pattern" "$code" "$payload" >>"$STUB_DIR/.$name.cases"
}

# stub_when_seen <name> <trigger-substring> <before-stdout> <after-stdout>
#
# A stub whose answer changes once some OTHER command has been called. This is how a test models the
# world actually changing: the cluster runs the old image tag until the merge happens, and the new
# one afterwards. Without it a static stub forces a test to pretend the rollout had already occurred
# before the PR merged, which then "proves" gates that are really just mis-modelled.
stub_when_seen() {
  local name="$1" trigger="$2" before="$3" after="$4"
  printf '%s\n' "$before" >"$STUB_DIR/.$name.before"
  printf '%s\n' "$after" >"$STUB_DIR/.$name.after"
  {
    echo '#!/usr/bin/env bash'
    printf 'printf "%%s %%s\\n" "%s" "$*" >> "%s"\n' "$name" "$STUB_LOG"
    printf 'if grep -qF -- %q "%s"; then cat "%s"; else cat "%s"; fi\n' \
      "$trigger" "$STUB_LOG" "$STUB_DIR/.$name.after" "$STUB_DIR/.$name.before"
    echo 'exit 0'
  } >"$STUB_DIR/$name"
  chmod +x "$STUB_DIR/$name"
}

# calls_to <name> — every recorded invocation of a stub, one per line, argv included.
calls_to() {
  grep "^$1 " "$STUB_LOG" || true
}

# called_with <name> <substring> — succeeds when some invocation's argv contained the substring.
called_with() {
  calls_to "$1" | grep -qF -- "$2"
}

# never_called <name> — succeeds when the stub was not invoked at all. The safety assertion: it is
# how a test proves the script REFUSED to merge or sync rather than merely happening not to.
never_called() {
  ! grep -q "^$1 " "$STUB_LOG"
}

# not_called_with <name> <substring> — succeeds when NO invocation contained the substring.
#
# USE THIS INSTEAD OF `! called_with …`. Under `set -e` — which is how bats detects a failed
# assertion — POSIX exempts "any command whose return value is being inverted with !" from the
# error trap. So a bare `! called_with git 'push'` NEVER fails a test, whatever the script did.
#
# Found 2026-08-24: a test written to prove the loop does not delete a branch backing an open PR
# passed against code that deletes it unconditionally. The inversion has to live INSIDE a function,
# so the caller invokes it as a plain command whose non-zero status set -e will actually catch.
# Same family as asserting only a non-zero exit (passes on 127) — an assertion that cannot fail.
not_called_with() {
  ! calls_to "$1" | grep -qF -- "$2"
}

# extract_configmap_script <manifest> <key> — write the ConfigMap value at data.<key> to stdout.
#
# The staleness decision logic lives in a ConfigMap inside the CronJob manifest so that the cluster
# runs the SAME text the tests exercise. Pulling it back out here is what makes that single source
# of truth real; without it the manifest and a tested copy would drift silently. Deliberately awk
# and not python/yq: the bats container is bare Alpine and this must work with busybox alone.
extract_configmap_script() {
  local manifest="$1" key="$2"
  # The block-scalar rule, followed properly: the value is every line indented deeper than the key,
  # and it ends at the first non-blank line that is not. Stopping only on `^  [^ ]` (the first
  # attempt) let the NEXT document's `---`, `apiVersion:` and `kind:` lines fall into the extracted
  # script — which then still "passed" the grep-shaped assertions while being garbage.
  awk -v key="$key" '
    $0 ~ "^  " key ": \\|"                  { grabbing = 1; next }
    grabbing && !/^    / && !/^[ \t]*$/     { grabbing = 0 }
    grabbing                                { sub(/^    /, ""); print }
  ' "$manifest"
}
