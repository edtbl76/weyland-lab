#!/usr/bin/env bats
# B216 — the ONNX export pins. onnx_export.py's decisions are covered in test_onnx_export.py; this asserts what pytest
# cannot: every service builds with the SAME script (four copies, one per Docker build context, drift silently), every
# service's spec pins real commits with recorded output, and no Dockerfile exports a model any other (unpinned) way.

setup() {
  load helper
  SERVICES="$REPO_ROOT/nodes/mother/lab/weyland-platform/services"
  EXPORTERS="weyland-dagster weyland-tool-server weyland-agent weyland-guard"
}

@test "every service's onnx_export.py is byte-identical to scripts/onnx_export.py" {
  for s in $EXPORTERS; do
    run cmp "$REPO_ROOT/scripts/onnx_export.py" "$SERVICES/$s/onnx_export.py"
    [ "$status" -eq 0 ] || { echo "DRIFT in $s — cp scripts/onnx_export.py $SERVICES/$s/"; return 1; }
  done
}

@test "every service's onnx_models.json loads: pinned commits, a probe, recorded output" {
  for s in $EXPORTERS; do
    run python3 -c "import sys; sys.path.insert(0, '$REPO_ROOT/scripts'); import onnx_export as o; \
s = o.load_spec('$SERVICES/$s/onnx_models.json'); print(len(s['models']), 'model(s)')"
    [ "$status" -eq 0 ] || { echo "$s: $output"; return 1; }
    [[ "$output" == *"model(s)"* ]]
  done
}

@test "each export stage runs the pinned export-and-check, and no Dockerfile calls from_pretrained itself" {
  for s in $EXPORTERS; do
    run grep -c 'RUN python /tmp/onnx/onnx_export.py build /tmp/onnx/onnx_models.json' "$SERVICES/$s/Dockerfile"
    [ "$output" = "1" ] || { echo "$s: the export stage does not run onnx_export.py build"; return 1; }
  done
  run grep -l 'from_pretrained' $(find "$SERVICES" -name 'Dockerfile*')
  [ "$status" -eq 1 ]          # grep found nothing: no Dockerfile exports a model outside the pinned path
}

@test "a spec that names a branch instead of a commit is refused, naming the model (exit 2, never a pass)" {
  spec="$(mktemp)"
  python3 - "$SERVICES/weyland-agent/onnx_models.json" "$spec" <<'PY'
import json, sys
s = json.load(open(sys.argv[1])); s["models"][0]["revision"] = "main"; json.dump(s, open(sys.argv[2], "w"))
PY
  run python3 "$REPO_ROOT/scripts/onnx_export.py" build "$spec"
  rm -f "$spec"
  [ "$status" -eq 2 ]
  [[ "$output" == *"BAD SPEC — BAAI/bge-base-en-v1.5: \`revision\` must be a 40-hex commit SHA, got 'main'"* ]]
}
