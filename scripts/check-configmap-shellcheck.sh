#!/usr/bin/env bash
# Shellcheck the shell scripts that live INSIDE k8s ConfigMaps (B230, 2026-10-19).
#
# WHY THIS EXISTS: CI's `shellcheck` step globs `scripts/**`, so a script written straight into a ConfigMap and run by
# a CronJob (pr-staleness, port-pr-reconcile, cron-freshness, image-provenance, the scan-suite and sonar-scan-repos
# runners, feast-ui's launcher) was never linted. Found closing B229, whose first draft of the sonar-scan-repos runner
# called a tool its image lacks — caught by hand, not by CI. Copies of scripts/ files (embed-*.sh) are checked here too:
# the same text, so it costs nothing and catches an embed that drifted from its source.
#
# Every ConfigMap `data` key ending in `.sh` under the platform's k8s/ tree, and every script passed inline as
# `sh -c '<script>'` (or bash/ash) in a workload container's command/args (2026-10-21, B230 re-audit: 37 of them, e.g.
# the sonar-scan-repos clone loop, were never linted), is written to a temp file and checked at CI's severity. A finding
# is reported as `<manifest>:<key>:<line>:<col>: …` or `<manifest>:<Kind>/<name>/<container>:<line>:<col>: …`.
#
#   usage: scripts/check-configmap-shellcheck.sh
# EXIT: 0 every script clean · 1 a finding, named · 2 could not check (no k8s dir, a manifest that does not parse, the
#   extractor failing, zero scripts found, no shellcheck, shellcheck itself erroring) — never a clean pass over nothing.
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

# Extract: one file per script, plus an index line "<file>\t<label>". ANY extractor failure is exit 2 (could not
# check): a manifest that won't parse, and also python unable to import yaml, which under `set -e` read as a finding.
if ! python3 - "$K8S_DIR" "$OUT" <<'PY'
import glob, os, sys
import yaml
k8s, out = sys.argv[1:]
n = 0
index = []
shells = {"sh", "bash", "ash"}


def containers(doc):
    """(container) for every init/regular container of a workload document; [] for anything else."""
    kind, spec = doc.get("kind"), doc.get("spec") or {}
    if kind == "CronJob":
        spec = ((spec.get("jobTemplate") or {}).get("spec") or {}).get("template", {}).get("spec") or {}
    elif kind in ("Deployment", "StatefulSet", "DaemonSet", "Job"):
        spec = (spec.get("template") or {}).get("spec") or {}
    elif kind != "Pod":
        return []
    return (spec.get("initContainers") or []) + (spec.get("containers") or [])


def add(body, label):
    global n
    n += 1
    name = os.path.join(out, f"{n:04d}.sh")
    with open(name, "w", encoding="utf-8") as f:
        f.write(body)
    index.append(f"{name}\t{label}")


inline = 0
for path in sorted(glob.glob(os.path.join(k8s, "**", "*.y*ml"), recursive=True)):
    rel = os.path.relpath(path, k8s)
    try:
        with open(path, encoding="utf-8") as f:
            docs = list(yaml.safe_load_all(f))
    except yaml.YAMLError as e:
        print(f"CANNOT CHECK: {rel} does not parse: {str(e).splitlines()[0]}", file=sys.stderr)
        sys.exit(2)
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        if doc.get("kind") == "ConfigMap":
            for key, body in (doc.get("data") or {}).items():
                if str(key).endswith(".sh") and isinstance(body, str):
                    add(body, f"{rel}:{key}")
            continue
        for c in containers(doc):
            argv = [str(a) for a in (c.get("command") or []) + (c.get("args") or [])]
            for i in range(1, len(argv) - 1):
                if argv[i] == "-c" and argv[i - 1].rsplit("/", 1)[-1] in shells:
                    # The `#!/bin/sh` line keeps shellcheck's line numbers one ahead of the script's, as for a key.
                    add("#!/bin/sh\n" + argv[i + 1], f"{rel}:{doc['kind']}/{doc['metadata']['name']}/{c.get('name')}")
                    inline += 1
with open(os.path.join(out, "index.tsv"), "w", encoding="utf-8") as f:
    f.write("\n".join(index) + ("\n" if index else ""))
with open(os.path.join(out, "inline.count"), "w", encoding="utf-8") as f:
    f.write(str(inline))
PY
then
  echo "CANNOT CHECK: extracting the scripts failed (see above) — not a finding, the check never ran" >&2; exit 2
fi

total=$(grep -c . "$OUT/index.tsv" || true)
if [ "${total:-0}" -eq 0 ]; then
  echo "CANNOT CHECK: no ConfigMap shell script found under $K8S_DIR — refusing to report a clean tree" >&2; exit 2
fi

bad=0
while IFS=$'\t' read -r file label; do
  rc=0; findings="$(shellcheck --severity=warning -f gcc "$file" 2>&1)" || rc=$?
  if [ "$rc" -ge 2 ]; then   # 1 = findings; 2+ = shellcheck could not run (bad file, bad option): never a finding
    printf '%s\n' "${findings//$file/$label}" >&2
    echo "CANNOT CHECK: shellcheck exited $rc on $label" >&2; exit 2
  elif [ "$rc" -eq 1 ]; then
    bad=$((bad + 1))
    printf '%s\n' "${findings//$file/$label}"
  fi
done < "$OUT/index.tsv"

if [ "$bad" -gt 0 ]; then
  echo "CONFIGMAP SHELLCHECK: $bad of $total shell script(s) have findings at --severity=warning."
  exit 1
fi
inline=$(cat "$OUT/inline.count")
echo "OK — $total shell script(s) ($((total - inline)) ConfigMap key(s), $inline inline sh -c) under $(basename "$(dirname "$K8S_DIR")")/k8s pass shellcheck --severity=warning."
