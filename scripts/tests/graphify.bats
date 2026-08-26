#!/usr/bin/env bats
# Wrapper around graphify (EMA-191, Stage 1 + 2b of docs/concepts/graphify-adoption.md).
#
# WHY A WRAPPER AND NOT THE RAW TOOL. Two reasons, both learned during the evaluation:
#
#   1. THE GRAPH IS BLIND TO SHELL. Bash `source` is not a dependency edge — measured across the full
#      repo graph: .ts 7102 edges / 1029 import-type, .py 3460 / 448, .sh 192 / **0**. So
#      `graphify affected common.sh` prints "No affected nodes found", which is BYTE-IDENTICAL to the
#      answer for a genuinely unused file. The wrapper must refuse to answer from the graph for shell
#      targets rather than pass that silence through.
#
#   2. IT MUST BE FED TRACKED FILES. The working tree is 927 MB (.terraform provider binaries, venvs);
#      tracked source is 24 MB. Pointed at the raw directory it would try to parse build artifacts.
#
# Everything lives OUTSIDE the repo — the copy, the venv and the graph — so no `graphify-out/` can
# ever land in a commit. The adoption doc originally said to gitignore it; not generating it inside
# the repo at all is strictly better.
#
# EXIT CODES follow the house convention: 1 = a real answer that happens to be a finding, 2 = the
# wrapper could not do its job. A missing venv or a missing graph must never read as "no impact".

setup() {
  load helper
  setup_stubs
  GUARD="$REPO_ROOT/scripts/graphify.sh"
}

teardown() {
  teardown_stubs
}

lib_source() {
  GRAPHIFY_LIB=1 source "$GUARD"
}

@test "the wrapper exists" {
  [ -f "$GUARD" ]
}

# --- the shell decision (Stage 2b) ----------------------------------------------------------------

@test "is_shell_target: .sh and .bash are shell" {
  lib_source
  for t in check-doc-counts.sh lib/common.sh some/path/ship-images.sh helper.bash; do
    run is_shell_target "$t"
    [ "$status" -eq 0 ]
  done
}

@test "is_shell_target: symbols and other languages are NOT shell" {
  lib_source
  for t in Verdict GuardrailPipeline verdict.py aidlc-lib.ts main.tf; do
    run is_shell_target "$t"
    [ "$status" -ne 0 ]
  done
}

@test "a shell target NEVER reaches the graph — it says so and greps instead" {
  # The whole point of the wrapper. Passing the graph's silence through would be indistinguishable
  # from "nothing depends on this", which is how a blind spot becomes a wrong answer.
  lib_source
  run affected_shell "common.sh" "$REPO_ROOT/scripts"
  [ "$status" -eq 0 ]
  [[ "$output" == *"not in the graph"* ]]
  # 13 scripts really do source lib/common.sh
  [ "$(printf '%s' "$output" | grep -c 'check-\|ship-images\|build-push\|pr-agent')" -ge 10 ]
}

@test "affected_shell reports SOURCERS, not files that merely mention the name" {
  # Found on the first real run: `scripts/graphify.sh` was reported as depending on common.sh purely
  # because its comments discuss it. A dependency check that counts prose is reporting a phantom —
  # the same class of wrong answer as the silent zero this function exists to replace.
  lib_source
  mkdir -p "$STUB_DIR/s"
  printf '#!/bin/bash\n. "$(dirname "$0")/lib/common.sh"\necho real\n' > "$STUB_DIR/s/real-user.sh"
  printf '#!/bin/bash\n# this script talks about lib/common.sh but never sources it\n' > "$STUB_DIR/s/just-mentions.sh"
  run affected_shell "common.sh" "$STUB_DIR/s"
  [ "$status" -eq 0 ]
  [[ "$output" == *"real-user.sh"* ]]
  [[ "$output" != *"just-mentions.sh"* ]]
}

@test "affected_shell matches both source spellings: '.' and 'source'" {
  lib_source
  mkdir -p "$STUB_DIR/s2"
  printf '#!/bin/bash\n. "$(dirname "$0")/lib/common.sh"\n'      > "$STUB_DIR/s2/dot.sh"
  printf '#!/bin/bash\nsource "$(dirname "$0")/lib/common.sh"\n' > "$STUB_DIR/s2/word.sh"
  run affected_shell "common.sh" "$STUB_DIR/s2"
  [[ "$output" == *"dot.sh"* ]]
  [[ "$output" == *"word.sh"* ]]
}

@test "affected_shell reports honestly when nothing references the file" {
  lib_source
  run affected_shell "definitely-not-a-real-lib.sh" "$REPO_ROOT/scripts"
  [ "$status" -eq 0 ]
  [[ "$output" == *"no references"* ]]
}

@test "affected_shell on an unreadable search root is FATAL, not empty" {
  lib_source
  run affected_shell "common.sh" "$STUB_DIR/nope"
  [ "$status" -ne 0 ]
}

# --- failing closed --------------------------------------------------------------------------------

@test "a missing venv is exit 2 with the build command, never a clean answer" {
  GRAPHIFY_VENV="$STUB_DIR/no-venv" run bash "$GUARD" affected Verdict
  [ "$status" -eq 2 ]
  [[ "$output" == *"venv"* ]]
  [[ "$output" == *"build"* ]]
}

@test "a missing graph is exit 2 and names the build command" {
  # "No affected nodes found" and "there is no graph" must never be the same answer.
  mkdir -p "$STUB_DIR/venv/bin"
  printf '#!/bin/sh\nexit 0\n' > "$STUB_DIR/venv/bin/graphify"; chmod +x "$STUB_DIR/venv/bin/graphify"
  GRAPHIFY_VENV="$STUB_DIR/venv" GRAPHIFY_GRAPH="$STUB_DIR/absent.json" run bash "$GUARD" affected Verdict
  [ "$status" -eq 2 ]
  [[ "$output" == *"build"* ]]
}

@test "no subcommand prints usage and exits 2" {
  run bash "$GUARD"
  [ "$status" -eq 2 ]
  [[ "$output" == *"usage"* ]]
}

@test "an unknown subcommand is exit 2, not silently ignored" {
  run bash "$GUARD" frobnicate
  [ "$status" -eq 2 ]
}

# --- dispatch --------------------------------------------------------------------------------------

@test "a non-shell target is handed to graphify with the graph path" {
  mkdir -p "$STUB_DIR/venv/bin"
  cat > "$STUB_DIR/venv/bin/graphify" <<'SH'
#!/bin/sh
echo "GRAPHIFY-CALLED: $*"
SH
  chmod +x "$STUB_DIR/venv/bin/graphify"
  printf '{"nodes":[],"links":[]}' > "$STUB_DIR/graph.json"
  GRAPHIFY_VENV="$STUB_DIR/venv" GRAPHIFY_GRAPH="$STUB_DIR/graph.json" run bash "$GUARD" affected Verdict
  [ "$status" -eq 0 ]
  [[ "$output" == *"GRAPHIFY-CALLED:"*"affected"*"Verdict"* ]]
  [[ "$output" == *"$STUB_DIR/graph.json"* ]]
}

@test "a SHELL target never invokes graphify even when the graph exists" {
  # Belt and braces: the fallback must win over a perfectly healthy graph.
  mkdir -p "$STUB_DIR/venv/bin"
  cat > "$STUB_DIR/venv/bin/graphify" <<'SH'
#!/bin/sh
echo "GRAPHIFY-CALLED: $*"
SH
  chmod +x "$STUB_DIR/venv/bin/graphify"
  printf '{"nodes":[],"links":[]}' > "$STUB_DIR/graph.json"
  GRAPHIFY_VENV="$STUB_DIR/venv" GRAPHIFY_GRAPH="$STUB_DIR/graph.json" \
    run bash "$GUARD" affected lib/common.sh
  [ "$status" -eq 0 ]
  [[ "$output" != *"GRAPHIFY-CALLED"* ]]
  [[ "$output" == *"not in the graph"* ]]
}

@test "god-nodes is passed through with the graph path" {
  mkdir -p "$STUB_DIR/venv/bin"
  cat > "$STUB_DIR/venv/bin/graphify" <<'SH'
#!/bin/sh
echo "GRAPHIFY-CALLED: $*"
SH
  chmod +x "$STUB_DIR/venv/bin/graphify"
  printf '{"nodes":[],"links":[]}' > "$STUB_DIR/graph.json"
  GRAPHIFY_VENV="$STUB_DIR/venv" GRAPHIFY_GRAPH="$STUB_DIR/graph.json" run bash "$GUARD" god-nodes 5
  [ "$status" -eq 0 ]
  [[ "$output" == *"god-nodes"* ]]
}
