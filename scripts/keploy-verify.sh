#!/usr/bin/env bash
# On-demand Keploy API-regression (B104). Replays the committed corpus under keploy/keploy/<test-set>/
# against a fresh launch of the app and diffs the responses.
#
# ON-DEMAND, on the HOST (rogueone) — NOT in CI. keploy needs privileged eBPF + docker and auto-elevates
# with sudo, which the k8s-backend Woodpecker step pods can't grant (see docs/runbooks/woodpecker-step-menu.md
# "Off-menu"). The `-c` command + port + health gate come from keploy/keploy.yml (single source of truth).
#
#   usage: bash scripts/keploy-verify.sh
#   exit:  keploy's — 0 = suite green, non-zero = a replay diff (regression) or keploy could not run.
set -uo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KEPLOY_DIR="$REPO_ROOT/keploy"

die() { printf 'keploy-verify: %s\n' "$*" >&2; exit 2; }
[ -f "$KEPLOY_DIR/keploy.yml" ] || die "no keploy/keploy.yml"
command -v keploy >/dev/null 2>&1 || die "keploy not installed — curl --silent -L https://keploy.io/install.sh | bash"

# The docker-run command lives in keploy.yml so it stays in step with record; pull it from there rather
# than duplicating the (Ray-avoiding, same-port) invocation here.
CMD="$(sed -n 's/^command: "\(.*\)"/\1/p' "$KEPLOY_DIR/keploy.yml" | head -1)"
[ -n "$CMD" ] || die "could not read \`command:\` from keploy.yml"

cd "$KEPLOY_DIR" || die "cannot cd into $KEPLOY_DIR"
# --health-path /health so replay starts as soon as the app answers, instead of waiting out keploy's
# 3-minute reserved-path readiness timeout (the golden app 404s the reserved path).
exec keploy test -c "$CMD" --mappings --health-path /health
