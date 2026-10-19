#!/usr/bin/env bash
# Shellcheck the shell scripts that live INSIDE k8s ConfigMaps (B230, 2026-10-19).
#
# WHY THIS EXISTS: CI's `shellcheck` step globs `scripts/**`, so a script written straight into a ConfigMap and run by
# a CronJob (pr-staleness, port-pr-reconcile, cron-freshness, image-provenance, the scan-suite and sonar-scan-repos
# runners, feast-ui's launcher) was never linted. Found closing B229, whose first draft of the sonar-scan-repos runner
# called a tool its image lacks — caught by hand, not by CI. Copies of scripts/ files (embed-*.sh) are checked here too:
# the same text, so it costs nothing and catches an embed that drifted from its source.
#
# Every ConfigMap `data` key ending in `.sh` under the platform's k8s/ tree is written to a temp file and checked at
# CI's severity. A finding is reported as `<manifest>:<key>:<line>:<col>: <level>: <message>`.
#
#   usage: scripts/check-configmap-shellcheck.sh
# EXIT: 0 every script clean · 1 a finding, named · 2 could not check (no k8s dir, a manifest that does not parse,
#   zero scripts found, no shellcheck) — never a clean pass over nothing.
# Tests: scripts/tests/configmap-shellcheck.bats. Runbook: docs/runbooks/code-quality.md.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
K8S_DIR="${CM_SHELLCHECK_K8S_DIR:-$PLATFORM_DIR/k8s}"

if ! command -v shellcheck >/dev/null 2>&1; then
  echo "CANNOT CHECK: shellcheck not found on PATH" >&2; exit 2
fi
if [ ! -d "$K8S_DIR" ]; then
  echo "CANNOT CHECK: no k8s directory at $K8S_DIR" >&2; exit 2
fi

OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT

# Extract: one file per script, plus an index line "<file>\t<manifest>:<key>". Exit 2 on a manifest that won't parse.
python3 - "$K8S_DIR" "$OUT" <<'PY'
import glob, os, sys
import yaml
k8s, out = sys.argv[1:]
n = 0
index = []
for path in sorted(glob.glob(os.path.join(k8s, "**", "*.y*ml"), recursive=True)):
    rel = os.path.relpath(path, k8s)
    try:
        with open(path, encoding="utf-8") as f:
            docs = list(yaml.safe_load_all(f))
    except yaml.YAMLError as e:
        print(f"CANNOT CHECK: {rel} does not parse: {str(e).splitlines()[0]}", file=sys.stderr)
        sys.exit(2)
    for doc in docs:
        if not isinstance(doc, dict) or doc.get("kind") != "ConfigMap":
            continue
        for key, body in (doc.get("data") or {}).items():
            if not str(key).endswith(".sh") or not isinstance(body, str):
                continue
            n += 1
            name = os.path.join(out, f"{n:04d}.sh")
            with open(name, "w", encoding="utf-8") as f:
                f.write(body)
            index.append(f"{name}\t{rel}:{key}")
with open(os.path.join(out, "index.tsv"), "w", encoding="utf-8") as f:
    f.write("\n".join(index) + ("\n" if index else ""))
PY

total=$(grep -c . "$OUT/index.tsv" || true)
if [ "${total:-0}" -eq 0 ]; then
  echo "CANNOT CHECK: no ConfigMap shell script found under $K8S_DIR — refusing to report a clean tree" >&2; exit 2
fi

bad=0
while IFS=$'\t' read -r file label; do
  if ! findings="$(shellcheck --severity=warning -f gcc "$file" 2>&1)"; then
    bad=$((bad + 1))
    printf '%s\n' "${findings//$file/$label}"
  fi
done < "$OUT/index.tsv"

if [ "$bad" -gt 0 ]; then
  echo "CONFIGMAP SHELLCHECK: $bad of $total ConfigMap shell script(s) have findings at --severity=warning."
  exit 1
fi
echo "OK — $total ConfigMap shell script(s) under $(basename "$(dirname "$K8S_DIR")")/k8s pass shellcheck --severity=warning."
