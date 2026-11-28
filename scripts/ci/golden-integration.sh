#!/usr/bin/env bash
# golden-integration.sh <ecosystem> — the golden paths' integration tier (B163 deep contract v2; B260).
#
# Runs every golden path's integration/ tests for one language ecosystem against REAL backends: Postgres, Valkey,
# Redpanda and MinIO, which the `golden-integration` workflow starts as Woodpecker services (sidecars). Nothing is
# mocked. Settings come from the environment (GOLDEN_DATABASE_URL, GOLDEN_VALKEY_URL, GOLDEN_KAFKA_BOOTSTRAP,
# GOLDEN_S3_ENDPOINT, ...).
#
# Fails closed: exit 2 for an unknown ecosystem, a backend that does not answer within INTEGRATION_WAIT_S (default
# 180) or no path with integration tests (verifying nothing is not a pass); exit 1 when any path's tests fail, named.
# Tests: scripts/tests/golden-integration.bats. Design: docs/concepts/golden-path-capabilities.md.
set -uo pipefail

# shellcheck source=scripts/lib/junit.sh
. "$(cd "$(dirname "$0")/.." && pwd)/lib/junit.sh"   # wrap_bare_cases(): Trunk counts bare <testcase>s as 0

ecosystem="${1:-}"
root="${GOLDEN_PATHS_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)/golden-paths}"
wait_s="${INTEGRATION_WAIT_S:-180}"
junit="${LANG_JUNIT_DIR:-reports/junit}"

# Per ecosystem: the golden paths, how a path is recognised as having integration tests, and how they run.
case "$ecosystem" in
  python) dirs=("$root"/python/*/) pattern='integration/test_*.py' ;;
  node)   dirs=("$root"/node/*/)   pattern='integration/*.integration.js' ;;
  *) echo "golden-integration: unknown ecosystem '$ecosystem' (known: python, node)" >&2; exit 2 ;;
esac

# run_python / run_node <dir> <junit file>: install the path's clients, then its integration tests. Exit 1 at the
# install marks it "(client install)"; any other failure is the tests'.
run_python() {
  (cd "$1" && pip install --quiet --no-cache-dir -r requirements-test.txt -r requirements-integration.txt) || return 10
  (cd "$1" && pytest -q -p no:cacheprovider integration --junitxml="$2")
}

# Node (B262): the clients are devDependencies, so `npm ci` installs them from the lockfile. A path with a build
# script (TypeScript) is built first: its integration tests load dist/. The tests are *.integration.js, never
# *.test.js, so the unit lanes never discover them; node's own runner writes the JUnit report.
run_node() {
  (cd "$1" && npm ci --no-audit --no-fund --loglevel=error) || return 10
  if grep -q '"build"[[:space:]]*:' "$1/package.json"; then
    (cd "$1" && npm run --silent build) || return 10
  fi
  local rc=0
  (cd "$1" && node --test --test-reporter=spec --test-reporter-destination=stdout \
      --test-reporter=junit --test-reporter-destination="$2" integration/*.integration.js) || rc=$?
  wrap_bare_cases "$2"        # node puts top-level test() cases straight under <testsuites>: Trunk counts those as 0
  return "$rc"
}

# host:port of each backend, from its URL (scheme://[user[:pass]@]host:port[/...]) or a bare host:port.
hostport() { local u="${1#*://}"; u="${u##*@}"; echo "${u%%/*}"; }

wait_for() { # wait_for <name> <host:port>
  local name="$1" hp="$2" deadline=$((SECONDS + wait_s))
  until (exec 3<>"/dev/tcp/${hp%:*}/${hp##*:}") 2>/dev/null; do
    if [ "$SECONDS" -ge "$deadline" ]; then
      echo "golden-integration: backend $name ($hp) unreachable after ${wait_s}s" >&2
      return 1
    fi
    sleep 2
  done
  echo "golden-integration: $name answers at $hp"
}

for pair in "postgres:${GOLDEN_DATABASE_URL:-}" "valkey:${GOLDEN_VALKEY_URL:-}" \
            "redpanda:${GOLDEN_KAFKA_BOOTSTRAP:-}" "minio:${GOLDEN_S3_ENDPOINT:-}"; do
  name="${pair%%:*}" url="${pair#*:}"
  [ -n "$url" ] || { echo "golden-integration: backend $name has no setting; unreachable" >&2; exit 2; }
  wait_for "$name" "$(hostport "$url")" || exit 2
done

# trunk-upload.sh reads <dir>/<source>/*.xml, one source per subdirectory (CI #740: a top-level file was "no JUnit
# reports"); the source is this step's name. Absolute NOW: each path's tests run after a cd (CI #739).
mkdir -p "$junit/integration-$ecosystem"
junit="$(cd "$junit/integration-$ecosystem" && pwd)"
ran=0 failed=()
for dir in "${dirs[@]}"; do
  dir="${dir%/}"
  compgen -G "$dir/$pattern" >/dev/null || continue
  path="${dir#"$root"/}" ran=$((ran + 1))
  echo "=== integration: $path ==="
  "run_$ecosystem" "$dir" "$junit/${path//\//-}.xml"
  case $? in
    0) ;;
    10) failed+=("$path (client install)") ;;
    *) failed+=("$path") ;;
  esac
done

if [ "$ran" -eq 0 ]; then
  echo "golden-integration: no integration tests found for $ecosystem under $root; nothing was verified" >&2
  exit 2
fi
if [ "${#failed[@]}" -gt 0 ]; then
  echo "golden-integration: FAILED: ${failed[*]}" >&2
  exit 1
fi
echo "golden-integration: $ecosystem OK ($ran path(s))"
