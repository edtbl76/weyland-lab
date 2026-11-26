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

ecosystem="${1:-}"
root="${GOLDEN_PATHS_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)/golden-paths}"
wait_s="${INTEGRATION_WAIT_S:-180}"
junit="${LANG_JUNIT_DIR:-reports/junit}"

case "$ecosystem" in
  python) dirs=("$root"/python/*/) ;;
  *) echo "golden-integration: unknown ecosystem '$ecosystem' (known: python)" >&2; exit 2 ;;
esac

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

mkdir -p "$junit"
junit="$(cd "$junit" && pwd)"   # absolute NOW: each path's tests run after a cd (CI #739 lost its report that way)
ran=0 failed=()
for dir in "${dirs[@]}"; do
  dir="${dir%/}"
  compgen -G "$dir/integration/test_*.py" >/dev/null || continue
  path="${dir#"$root"/}" ran=$((ran + 1))
  echo "=== integration: $path ==="
  if ! (cd "$dir" && pip install --quiet --no-cache-dir -r requirements-test.txt -r requirements-integration.txt); then
    failed+=("$path (client install)"); continue
  fi
  (cd "$dir" && pytest -q -p no:cacheprovider integration \
      --junitxml="$junit/golden-integration-${path//\//-}.xml") || failed+=("$path")
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
