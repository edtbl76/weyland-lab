#!/usr/bin/env bats
# Tests for check-onnx-sync.sh (U13 architecture guard). Proves the fail-closed exit contract by REASON,
# not just exit sign: 0 identical bodies · 1 drift · 2 cannot-run. The guard compares the OnnxBge METHOD
# BODIES modulo docstring, so the fixtures cover the docstring-agnostic case the verdict guard doesn't have.
# Paths are overridden via ONNX_A/ONNX_B.

setup() {
  GUARD="${BATS_TEST_DIRNAME}/../check-onnx-sync.sh"
  TMP="$(mktemp -d)"
}
teardown() { rm -rf "$TMP"; }

# Writes an OnnxBge class to $1 with docstring $2 and a get_text_embedding returning $3.
_mk() {
  cat > "$1" <<PY
class OnnxBge:
    "$2"
    def __init__(self, model_dir):
        self._dir = model_dir
    def get_text_embedding(self, text):
        return [$3]
PY
}

@test "identical bodies with DIFFERENT docstrings pass exit 0 (docstring is ignored)" {
  _mk "$TMP/a.py" "doc for tool-server" "1.0"
  _mk "$TMP/b.py" "a totally different docstring naming its own sibling" "1.0"
  run env ONNX_A="$TMP/a.py" ONNX_B="$TMP/b.py" bash "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"identical"* ]]
}

@test "a changed method body is DRIFT exit 1, with the reason" {
  _mk "$TMP/a.py" "doc" "1.0"
  _mk "$TMP/b.py" "doc" "2.0"
  run env ONNX_A="$TMP/a.py" ONNX_B="$TMP/b.py" bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"DRIFT"* ]]
}

@test "a missing file is CANNOT-RUN exit 2, never a false pass" {
  _mk "$TMP/a.py" "doc" "1.0"
  run env ONNX_A="$TMP/a.py" ONNX_B="$TMP/does-not-exist.py" bash "$GUARD"
  [ "$status" -eq 2 ]
  [[ "$output" == *"CANNOT RUN"* ]]
}

@test "a file with no OnnxBge class is CANNOT-RUN exit 2, not a false pass" {
  _mk "$TMP/a.py" "doc" "1.0"
  printf 'x = 1\n' > "$TMP/b.py"
  run env ONNX_A="$TMP/a.py" ONNX_B="$TMP/b.py" bash "$GUARD"
  [ "$status" -eq 2 ]
  [[ "$output" == *"CANNOT RUN"* ]]
}

@test "the real repo copies are in sync (the live invariant)" {
  run bash "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"identical"* ]]
}
