#!/usr/bin/env bats
# scripts/sync-golden-shared.sh — one source for code every golden path of a language shares (B261, owner: "One
# source, synced copies"). Each path must stay self-contained (image builds and new-service.sh see only its own
# directory), so the source in golden-paths-shared/<lang>/ is COPIED into every path that opts in with a
# `.golden-shared` marker, stamped as generated; --check (a repo guard) fails on any drift.

setup() {
  SYNC="$BATS_TEST_DIRNAME/../sync-golden-shared.sh"
  ROOT="$(mktemp -d)"; export REPO_ROOT="$ROOT"
  mkdir -p "$ROOT/golden-paths-shared/python/integration" "$ROOT/golden-paths/python/a" "$ROOT/golden-paths/python/b"
  printf 'X = 1\n' > "$ROOT/golden-paths-shared/python/items_store.py"
  printf 'def test(): pass\n' > "$ROOT/golden-paths-shared/python/integration/test_items.py"
  : > "$ROOT/golden-paths/python/a/.golden-shared"          # a opts in; b does not
}

teardown() { rm -rf "$ROOT"; }

@test "sync copies every shared file into each opted-in path, stamped as generated" {
  run bash "$SYNC"
  [ "$status" -eq 0 ]
  head -1 "$ROOT/golden-paths/python/a/items_store.py" | grep -q "GENERATED from golden-paths-shared/python/items_store.py"
  tail -n +2 "$ROOT/golden-paths/python/a/items_store.py" | cmp -s - "$ROOT/golden-paths-shared/python/items_store.py"
  [ -f "$ROOT/golden-paths/python/a/integration/test_items.py" ]
  [ ! -e "$ROOT/golden-paths/python/b/items_store.py" ]        # not opted in: untouched
}

@test "--check passes when every copy matches its source" {
  bash "$SYNC"
  run bash "$SYNC" --check
  [ "$status" -eq 0 ]
  [[ "$output" == *"in sync"* ]]
}

@test "--check fails on a hand-edited copy, naming it and the fix" {
  bash "$SYNC"
  printf 'X = 2\n' >> "$ROOT/golden-paths/python/a/items_store.py"
  run bash "$SYNC" --check
  [ "$status" -eq 1 ]
  [[ "$output" == *"golden-paths/python/a/items_store.py"* && "$output" == *"sync-golden-shared.sh"* ]]
}

@test "--check fails on a missing copy" {
  bash "$SYNC"
  rm "$ROOT/golden-paths/python/a/integration/test_items.py"
  run bash "$SYNC" --check
  [ "$status" -eq 1 ]
  [[ "$output" == *"integration/test_items.py"* ]]
}

@test "shared code with no opted-in path is exit 2: checking nothing is not a pass" {
  rm "$ROOT/golden-paths/python/a/.golden-shared"
  run bash "$SYNC" --check
  [ "$status" -eq 2 ]
  [[ "$output" == *"no golden path opts in"* ]]
}

@test "caches and bytecode are never copied" {
  mkdir -p "$ROOT/golden-paths-shared/python/__pycache__"
  : > "$ROOT/golden-paths-shared/python/__pycache__/items_store.cpython-312.pyc"
  run bash "$SYNC"
  [ "$status" -eq 0 ]
  [ ! -e "$ROOT/golden-paths/python/a/__pycache__" ]
}

@test "a JavaScript or TypeScript copy is stamped with a // comment, never # (B262: # is not a JS comment)" {
  mkdir -p "$ROOT/golden-paths-shared/node/src/shared" "$ROOT/golden-paths/node/x"
  printf 'module.exports = 1;\n' > "$ROOT/golden-paths-shared/node/src/shared/items-store.js"
  printf 'export const y = 1;\n' > "$ROOT/golden-paths-shared/node/src/shared/y.ts"
  : > "$ROOT/golden-paths/node/x/.golden-shared"
  run bash "$SYNC"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  head -1 "$ROOT/golden-paths/node/x/src/shared/items-store.js" | grep -q '^// GENERATED from golden-paths-shared/node/src/shared/items-store.js'
  head -1 "$ROOT/golden-paths/node/x/src/shared/y.ts" | grep -q '^// GENERATED from golden-paths-shared/node/src/shared/y.ts'
  head -1 "$ROOT/golden-paths/python/a/items_store.py" | grep -q '^# GENERATED'     # python keeps #
  run bash "$SYNC" --check
  [ "$status" -eq 0 ]
}

@test "--check fails on an orphaned copy whose source was renamed or removed, naming it (B262)" {
  bash "$SYNC"
  printf '# GENERATED from golden-paths-shared/python/old_name.py by scripts/sync-golden-shared.sh: edit the source, not this copy.\nX = 0\n' \
    > "$ROOT/golden-paths/python/a/old_name.py"
  run bash "$SYNC" --check
  [ "$status" -eq 1 ]
  [[ "$output" == *"ORPHAN: golden-paths/python/a/old_name.py"* ]] || { echo "$output"; return 1; }
}

@test "a write removes orphaned copies, so a rename never leaves a stale GENERATED file behind (B262)" {
  bash "$SYNC"
  printf '// GENERATED from golden-paths-shared/python/old_name.js by scripts/sync-golden-shared.sh: edit the source, not this copy.\n' \
    > "$ROOT/golden-paths/python/a/old_name.js"
  printf 'hand-written, not generated\n' > "$ROOT/golden-paths/python/a/mine.py"
  run bash "$SYNC"
  [ "$status" -eq 0 ]
  [ ! -e "$ROOT/golden-paths/python/a/old_name.js" ]
  [ -f "$ROOT/golden-paths/python/a/mine.py" ]                    # never touches a file it did not generate
  [[ "$output" == *"removed orphan golden-paths/python/a/old_name.js"* ]] || { echo "$output"; return 1; }
}
