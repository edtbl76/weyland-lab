#!/usr/bin/env bash
# Placement inventory guard (B198) — the repo-guards entrypoint. Logic lives in scripts/placement_check.py (tested by
# scripts/tests/test_placement_check.py); this wrapper exists so every guard in `.woodpecker.yml` is a
# `bash scripts/check-*.sh` call. Default mode is --repo (no cluster); the nightly placement-coverage CronJob runs
# `placement_check.py --live`. Exit 0 clean · 1 drift (named) · 2 could not read a source.
#   usage: scripts/check-placement.sh [--repo | --live | --migration] [--file F] [--model M] [--prometheus URL]
set -euo pipefail
exec python3 "$(dirname "${BASH_SOURCE[0]}")/placement_check.py" "$@"
