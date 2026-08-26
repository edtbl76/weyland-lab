#!/usr/bin/env bash
# Wrapper around graphify — impact analysis and architectural hubs (EMA-191).
#
# Plan + evaluation: docs/concepts/graphify-adoption.md. This is Stage 1 + Stage 2b.
#
#   usage: scripts/graphify.sh build              rebuild the graph from TRACKED source
#          scripts/graphify.sh affected <target>  what depends on this symbol or file
#          scripts/graphify.sh god-nodes [N]      most-connected nodes (architectural hubs)
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
GRAPHIFY_EXTRAS="${GRAPHIFY_EXTRAS:-terraform,neo4j,mcp,pdf,sql}"

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
  mkdir -p "$GRAPHIFY_HOME"
  python3 -m venv "$GRAPHIFY_VENV"
  "$GRAPHIFY_VENV/bin/pip" install -q --upgrade pip
  "$GRAPHIFY_VENV/bin/pip" install -q "${GRAPHIFY_PIN%%==*}[$GRAPHIFY_EXTRAS]==${GRAPHIFY_PIN##*==}"
  echo "installed $GRAPHIFY_PIN [$GRAPHIFY_EXTRAS] into $GRAPHIFY_VENV"
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
  "$GRAPHIFY_VENV/bin/graphify" affected "$target" --graph "$GRAPHIFY_GRAPH"
}

cmd_god_nodes() {
  require_venv
  require_graph
  "$GRAPHIFY_VENV/bin/graphify" god-nodes --graph "$GRAPHIFY_GRAPH" --top "${1:-10}"
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
    *)         usage ;;
  esac
}

if [ -z "${GRAPHIFY_LIB:-}" ]; then
  main "$@"
fi
