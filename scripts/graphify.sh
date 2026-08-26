#!/usr/bin/env bash
# Wrapper around graphify — impact analysis and architectural hubs (EMA-191).
#
# Plan + evaluation: docs/concepts/graphify-adoption.md. This is Stage 1 + Stage 2b.
#
#   usage: scripts/graphify.sh build              rebuild the graph from TRACKED source
#          scripts/graphify.sh affected <target>  what depends on this symbol or file
#          scripts/graphify.sh god-nodes [N]      most-connected nodes (architectural hubs)
#          scripts/graphify.sh verify [symbol]    prove the graph invents nothing (run after a pin bump)
#          scripts/graphify.sh install            create the venv (one-off)
#
# WHY A WRAPPER AND NOT THE RAW TOOL — two things the raw CLI gets wrong for this repo:
#
# 1. THE GRAPH IS BLIND TO SHELL, SILENTLY. Bash `source` is not a dependency edge. Measured across
#    the full repo graph: `.ts` 7102 edges / 1029 import-type, `.py` 3460 / 448, `.sh` 192 / **0**.
#    So `graphify affected common.sh` prints "No affected nodes found" — BYTE-IDENTICAL to the answer
#    for a genuinely unused file, when 13 scripts source it. Compare the `.sql` gap, which the tool
#    reports properly ("16 .sql files contributed nothing … tree_sitter_sql not installed"). Same
#    missing coverage, opposite reporting. This wrapper refuses to pass that silence through.
#
#    It is NOT worth constraining how this repo writes shell to preserve a grep substitute — an
#    earlier draft of the plan proposed exactly that and it was wrong. When a tool has a blind spot,
#    the fix belongs where you consume it. The standing rule instead: if a shell script needs a real
#    dependency chain it has outgrown shell, so rewrite that piece in Python. Shell that is correctly
#    scoped has nothing for `affected` to find.
#
# 2. IT MUST BE FED TRACKED FILES. The working tree is 927 MB — `.terraform/` provider binaries and
#    venvs under weyland-platform/scripts/ — against 24 MB of tracked source. Pointed at the raw
#    directory it parses build artifacts.
#
# NOTHING IS WRITTEN INSIDE THE REPO. The venv, the source copy and the graph all live under
# $GRAPHIFY_HOME. The adoption doc first said to gitignore `graphify-out/`; not generating it in the
# repo at all is strictly better — there is nothing to forget to ignore.
#
# EXIT CODES: 0 = answered. 1 = reserved for a finding. 2 = the wrapper could not do its job. A
# missing venv or graph is 2, never a clean "nothing found" — that substitution is the defect this
# whole family of guards exists to catch.
set -euo pipefail

GRAPHIFY_HOME="${GRAPHIFY_HOME:-$HOME/.local/share/weyland/graphify}"
GRAPHIFY_VENV="${GRAPHIFY_VENV:-$GRAPHIFY_HOME/venv}"
GRAPHIFY_SRC="${GRAPHIFY_SRC:-$GRAPHIFY_HOME/src}"
GRAPHIFY_GRAPH="${GRAPHIFY_GRAPH:-$GRAPHIFY_SRC/graphify-out/graph.json}"
# Pinned on purpose: 0.9.x, ~5 months old, 1130 open issues. Treat an upgrade as a change.
GRAPHIFY_PIN="${GRAPHIFY_PIN:-graphifyy==0.9.50}"
# `sql` is NOT optional here — without it 16 .sql files contribute nothing to the graph.
# `leiden` pulls graspologic, which is `requires_python: <3.13,>=3.9` — see venv_python below.
GRAPHIFY_EXTRAS="${GRAPHIFY_EXTRAS:-terraform,neo4j,mcp,pdf,sql,leiden}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- the shell decision (Stage 2b) ----------------------------------------------------------------

# is_shell_target <target> -> 0 when the graph cannot answer for it.
is_shell_target() { # is_shell_target <target>
  case "${1-}" in
    *.sh|*.bash) return 0 ;;
    *)           return 1 ;;
  esac
}

# affected_shell <file> <search-root> -> who sources it, by grep.
#
# Sound ONLY because shell dependencies here are one level deep and always will be: `lib/common.sh`
# is a leaf holding two path constants, and anything needing more structure should be Python. This is
# not a general shell resolver and must not grow into one.
affected_shell() { # affected_shell <file> <search-root>
  local target="${1:?usage: affected_shell <file> <search-root>}" root="${2:?}"
  local base; base="$(basename "$target")"
  [ -d "$root" ] || { echo "FATAL: search root does not exist: $root" >&2; return 2; }
  echo "shell dependencies are not in the graph (bash 'source' is not an edge) - grepping instead."
  # FILE SELECTION VIA `find`, NOT `grep --include`. On rogueone `grep` on PATH is **ugrep 7.8.4**,
  # not GNU grep (/usr/bin/grep is GNU 3.11, shadowed), and its `--include` did not restrict by
  # extension the way GNU's does here — it returned a `.bats` file for `--include='*.sh'`, which is
  # how this function first reported a phantom dependency. CI runs on alpine, a third implementation.
  # `find -name` is unambiguous in all three.
  # MATCH THE SOURCE STATEMENT, NOT THE NAME. A bare name match counts prose: this wrapper's own
  # comments discuss `common.sh` at length, and the first version duly reported graphify.sh as a
  # dependent. A check that counts comments reports phantoms, which is the same class of wrong answer
  # as the silent zero it replaces. `^\s*(\.|source)\s` anchors to an actual source statement and
  # covers both spellings.
  local hits
  hits="$(find "$root" -type f \( -name '*.sh' -o -name '*.bash' \) -print0 2>/dev/null \
          | xargs -0 -r grep -lE "^[[:space:]]*(\.|source)[[:space:]].*${base}" 2>/dev/null \
          | grep -v -- "/$base\$" || true)"
  if [ -z "$hits" ]; then
    echo "  no references to $base under $root"
    return 0
  fi
  printf '%s\n' "$hits" | sed "s|^$root/|  |"
}

# --- interpreter selection -------------------------------------------------------------------------

# venv_python -> the interpreter to build the venv with.
#
# Leiden comes from `graspologic`, which is `requires_python: <3.13,>=3.9`. rogueone's default python3
# is 3.13.3, so a plain `python3 -m venv` silently loses Leiden: graphify catches the ImportError and
# falls back to `networkx.community.louvain_communities` (graphify/cluster.py:67-76) without a word.
#
# Louvain is not wrong — it is Leiden's 2008 predecessor and the reason Leiden exists is that Louvain
# can emit badly-connected or internally-disconnected communities. But the choice must be deliberate
# and visible, not an accident of which interpreter happened to be first on PATH.
venv_python() {
  if [ -n "${GRAPHIFY_PYTHON:-}" ]; then printf '%s' "$GRAPHIFY_PYTHON"; return 0; fi
  local c
  for c in python3.12 python3.11 python3.10; do
    command -v "$c" >/dev/null 2>&1 && { printf '%s' "$c"; return 0; }
  done
  printf 'python3'
}

# leiden_status <venv> -> print which clustering the built venv will actually use.
#
# Asserted by IMPORTING it, not by inspecting the pin. A wheel that failed to build leaves the extra
# "installed" while the import fails, and the difference is invisible from the outside.
leiden_status() { # leiden_status <venv>
  local v="${1:?usage: leiden_status <venv>}"
  if "$v/bin/python" -c "import graspologic" >/dev/null 2>&1; then
    echo "clustering: Leiden (graspologic present)"
  else
    echo "clustering: networkx louvain fallback - graspologic absent (needs python < 3.13)"
  fi
}

# --- preconditions ---------------------------------------------------------------------------------

require_venv() {
  [ -x "$GRAPHIFY_VENV/bin/graphify" ] || {
    echo "FATAL: no graphify venv at $GRAPHIFY_VENV" >&2
    echo "       run: scripts/graphify.sh install   (then: scripts/graphify.sh build)" >&2
    exit 2
  }
}

require_graph() {
  [ -r "$GRAPHIFY_GRAPH" ] || {
    echo "FATAL: no graph at $GRAPHIFY_GRAPH" >&2
    echo "       run: scripts/graphify.sh build" >&2
    exit 2
  }
}

# --- subcommands -----------------------------------------------------------------------------------

cmd_install() {
  local py; py="$(venv_python)"
  mkdir -p "$GRAPHIFY_HOME"
  # --clear IS LOAD-BEARING. `python -m venv` over an existing directory REUSES it and will not swap
  # the interpreter, so re-running install after adding python3.12 kept a 3.13 venv and Leiden stayed
  # absent. It printed "interpreter: python3.12 (Python 3.13.3)" — selected one, got the other — and
  # only the leiden_status line below made that visible. Without --clear the install silently no-ops
  # on the thing you ran it to change.
  "$py" -m venv --clear "$GRAPHIFY_VENV"
  "$GRAPHIFY_VENV/bin/pip" install -q --upgrade pip
  "$GRAPHIFY_VENV/bin/pip" install -q "${GRAPHIFY_PIN%%==*}[$GRAPHIFY_EXTRAS]==${GRAPHIFY_PIN##*==}"
  echo "installed $GRAPHIFY_PIN [$GRAPHIFY_EXTRAS] into $GRAPHIFY_VENV"
  echo "interpreter: $py ($("$GRAPHIFY_VENV/bin/python" -V 2>&1))"
  leiden_status "$GRAPHIFY_VENV"
}

# TRACKED FILES ONLY — git ls-files, never the working tree. See the header for the 927 MB / 24 MB
# split and why it matters.
cmd_build() {
  require_venv
  command -v git >/dev/null 2>&1 || { echo "FATAL: git not on PATH" >&2; exit 2; }
  mkdir -p "$GRAPHIFY_SRC"
  ( cd "$REPO_ROOT" && git ls-files -z | rsync -a --delete-excluded --files-from=- --from0 ./ "$GRAPHIFY_SRC/" ) || {
    echo "FATAL: could not stage tracked source into $GRAPHIFY_SRC" >&2; exit 2; }
  "$GRAPHIFY_VENV/bin/graphify" update "$GRAPHIFY_SRC"
}

cmd_affected() {
  local target="${1:-}"
  [ -n "$target" ] || { echo "usage: scripts/graphify.sh affected <symbol-or-file>" >&2; exit 2; }
  # The shell branch is checked BEFORE any graph precondition: the answer does not come from the
  # graph, so a missing graph is irrelevant to it.
  if is_shell_target "$target"; then
    affected_shell "$target" "$REPO_ROOT/scripts"
    return $?
  fi
  require_venv
  require_graph
  local out rc=0
  out="$("$GRAPHIFY_VENV/bin/graphify" affected "$target" --graph "$GRAPHIFY_GRAPH" 2>&1)" || rc=$?
  printf '%s\n' "$out"
  # Turn the unactionable "No unique node match" into the list of colliding files.
  if printf '%s' "$out" | grep -q "No unique node match"; then
    candidates "$target" "$GRAPHIFY_GRAPH"
  fi
  return $rc
}

cmd_god_nodes() {
  require_venv
  require_graph
  "$GRAPHIFY_VENV/bin/graphify" god-nodes --graph "$GRAPHIFY_GRAPH" --top "${1:-10}"
}

# --- ambiguity ------------------------------------------------------------------------------------
#
# graphify answers an ambiguous symbol with the bare string "No unique node match for X" (the
# pre-#1504 node-ID scheme: IDs are not path-qualified, so same-named symbols in different files
# collide). That message names no candidates, so the reader cannot act on it.
#
# It bites hardest exactly where it matters most. `affected Decision` is unanswerable on this repo
# because there are two nodes labelled `decision` - one in weyland-guard/guardrails/verdict.py and one
# in the DUPLICATED weyland-tool-server copy. A shared type becomes unqueryable precisely when it has
# been duplicated, which is the moment the cascade question is worth asking.
candidates() { # candidates <symbol> <graph.json>
  local sym="${1:?usage: candidates <symbol> <graph.json>}" graph="${2:?}"
  [ -r "$graph" ] || { echo "FATAL: cannot read $graph" >&2; return 2; }
  python3 - "$graph" "$sym" <<'PY'
import json, sys
graph, sym = sys.argv[1], sys.argv[2].lower()
try:
    g = json.load(open(graph, encoding="utf-8"))
except Exception as exc:
    print(f"FATAL: could not parse {graph}: {exc}", file=sys.stderr); raise SystemExit(2)
hits = [n for n in (g.get("nodes") or [])
        if (n.get("norm_label") or n.get("label", "").lower()) == sym]
if not hits:
    print(f"  no node in the graph is labelled '{sys.argv[2]}'")
    raise SystemExit(0)
print(f"  {len(hits)} node(s) share this label - disambiguate by file:")
for n in hits:
    print(f"    {n.get('label')}  <-  {n.get('source_file') or '(no source)'}")
PY
}

# --- verify (run this after bumping GRAPHIFY_PIN) --------------------------------------------------
#
# WHY THIS EXISTS. Stage 1's acceptance — "affected matches a hand grep" — was checked once by hand
# and then left as an anecdote. The version pin guards drift while it holds, but NOTHING re-checks
# accuracy when someone bumps it, which is exactly when behaviour can change. A bats case could not
# cover this: it needs a built graph, so it would have to skip in CI, and a skipping guard is the
# advisory trap. A subcommand run deliberately at the moment of risk is the right shape.
#
# THE INVARIANT IS A SUBSET, NOT EQUALITY. graphify legitimately omits the definition site (a symbol
# is not "affected by" itself), so demanding equality with grep would fail for a correct answer. What
# it must NEVER do is name a file that does not contain the symbol at all — that is fabrication.

# graph_files <affected-output> -> the bare file paths it named, line numbers stripped.
graph_files() { # graph_files <affected-output>
  printf '%s\n' "${1-}" \
    | sed -n 's/.*\] \([^ ]*\):L[0-9]*.*/\1/p' \
    | sort -u
}

# verify_subset <symbol> <graph-files> <search-root>
verify_subset() { # verify_subset <symbol> <newline-separated-files> <search-root>
  local symbol="${1:?}" files="${2-}" root="${3:?}"
  # An empty result trivially satisfies "subset of grep". It must fail instead, or a completely
  # broken upgrade verifies clean — the absent-result-as-success trap, one level up.
  if [ -z "$(printf '%s' "$files" | tr -d '[:space:]')" ]; then
    echo "FATAL: graphify returned nothing for '$symbol' - that is not a pass." >&2
    return 1
  fi
  local f bad=0 abs
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    abs="$f"; [ -f "$abs" ] || abs="$root/${f#"$root/"}"
    if [ ! -f "$abs" ] || ! grep -q -- "$symbol" "$abs" 2>/dev/null; then
      echo "  FABRICATED: $f does not contain '$symbol'" >&2
      bad=$((bad + 1))
    fi
  done <<<"$files"
  [ "$bad" -eq 0 ] || { echo "FATAL: $bad file(s) named by the graph do not contain the symbol." >&2; return 1; }
  return 0
}

cmd_verify() {
  require_venv
  require_graph
  local symbol="${1:-GuardrailPipeline}"
  local root="$REPO_ROOT/nodes/mother/lab/weyland-platform/services"
  local out files
  out="$("$GRAPHIFY_VENV/bin/graphify" affected "$symbol" --graph "$GRAPHIFY_GRAPH" 2>&1)" || {
    echo "FATAL: graphify affected failed for '$symbol'" >&2; exit 2; }
  files="$(graph_files "$out")"
  echo "verifying '$symbol' - graph named $(printf '%s\n' "$files" | grep -c . || true) file(s)"
  if verify_subset "$symbol" "$files" "$REPO_ROOT"; then
    leiden_status "$GRAPHIFY_VENV"
    echo "OK - every file the graph named really contains '$symbol'."
    return 0
  fi
  echo "   Run after any GRAPHIFY_PIN bump. A pin bump is a change, not an upgrade." >&2
  exit 1
}

usage() {
  sed -n '4,8p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,2\}//'
  exit 2
}

main() {
  case "${1:-}" in
    install)   shift; cmd_install "$@" ;;
    build)     shift; cmd_build "$@" ;;
    affected)  shift; cmd_affected "$@" ;;
    god-nodes) shift; cmd_god_nodes "$@" ;;
    verify)    shift; cmd_verify "$@" ;;
    *)         usage ;;
  esac
}

if [ -z "${GRAPHIFY_LIB:-}" ]; then
  main "$@"
fi
