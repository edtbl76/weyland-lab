#!/usr/bin/env bash
# check-onnx-sync.sh — architecture guard (U13, DoD Pillar 8): the OnnxBge query-embedder class is
# duplicated across weyland-tool-server (main.py) and weyland-agent (retrievers.py). It is a BEHAVIORAL
# contract, not just shared code — both services must embed the SAME model with the SAME pooling
# (bge CLS + L2 normalize) or the agent's retrieval lands in a different vector space than the index the
# tool-server built, and results silently degrade. Nothing keeps the two copies in sync — the same
# duplication class DoD Pillar 8 flags for guardrails/verdict.py (see check-verdict-sync.sh).
#
# The class is EMBEDDED in a larger file and the two docstrings legitimately differ (each names its own
# sibling), so a byte diff would false-alarm. This compares the METHOD BODIES only: it parses each file,
# extracts the OnnxBge class, STRIPS the docstring, and compares the AST-normalized source — so formatting,
# comments, and the docstring don't matter, but any change to __init__ / get_text_embedding logic does.
#
# Fail-closed exit contract (estate convention): 0 = method bodies identical · 1 = they DRIFT (a real
# defect) · 2 = the guard could not run (a file/class is missing or unparseable) — never conflate
# "could not check" with "in sync".
#
#   usage: scripts/check-onnx-sync.sh
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Paths are overridable so the bats suite can point them at fixtures (estate convention).
A="${ONNX_A:-$here/nodes/mother/lab/weyland-platform/services/weyland-tool-server/main.py}"
B="${ONNX_B:-$here/nodes/mother/lab/weyland-platform/services/weyland-agent/retrievers.py}"

for f in "$A" "$B"; do
  [ -f "$f" ] || { printf 'CANNOT RUN — missing %s\n' "$f" >&2; exit 2; }
done

# The extractor prints the class's AST-normalized body (docstring stripped) to stdout, or nothing +
# a reason to stderr with exit 2 if the class is absent/unparseable. Two calls, compared in shell, so a
# python crash (exit 2) is never mistaken for a match.
extract() {
  ONNX_TARGET="$1" python3 - "$1" <<'PY'
import ast, os, sys
path = os.environ["ONNX_TARGET"]
try:
    tree = ast.parse(open(path).read())
except SyntaxError as e:
    print(f"CANNOT RUN — {path} does not parse: {e}", file=sys.stderr); sys.exit(2)
for node in ast.walk(tree):
    if isinstance(node, ast.ClassDef) and node.name == "OnnxBge":
        body = node.body[:]
        if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
           and isinstance(body[0].value.value, str):
            body = body[1:]  # drop the docstring — it legitimately differs per file
        if not body:
            print(f"CANNOT RUN — OnnxBge in {path} has no body after the docstring", file=sys.stderr); sys.exit(2)
        clone = ast.ClassDef(name="OnnxBge", bases=[], keywords=[], body=body, decorator_list=[])
        print(ast.unparse(ast.fix_missing_locations(clone)))
        sys.exit(0)
print(f"CANNOT RUN — no class OnnxBge found in {path}", file=sys.stderr); sys.exit(2)
PY
}

ca="$(extract "$A")" || exit 2
cb="$(extract "$B")" || exit 2

if [ "$ca" = "$cb" ]; then
  printf 'OK — OnnxBge method bodies are identical across weyland-tool-server and weyland-agent (%s normalized lines).\n' "$(printf '%s\n' "$ca" | wc -l)"
  exit 0
fi

printf 'DRIFT — OnnxBge differs between weyland-tool-server (main.py) and weyland-agent (retrievers.py):\n' >&2
diff <(printf '%s\n' "$ca") <(printf '%s\n' "$cb") >&2 || true
printf 'Both embed the SAME model into the SAME collections; if their pooling/inputs drift, the agent retrieves against a\n' >&2
printf 'vector space the index was not built in. Reconcile the two copies (docstrings may differ; the code may not).\n' >&2
exit 1
