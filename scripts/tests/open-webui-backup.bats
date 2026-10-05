#!/usr/bin/env bats
# open-webui-backup (2026-10-04, DoD pillar 9). The nightly CronJob runs the copy of scripts/open_webui_backup.py
# embedded in its ConfigMap, not the repo file — two copies of a backup drift silently, and a backup that drifted from
# its tested logic is untested. scripts/embed-open-webui-backup.sh regenerates the copy; this asserts it is identical.
# The behaviour itself is tested by scripts/tests/test_open_webui_backup.py (pytest).

setup() {
  REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)"
  MANIFEST="$REPO_ROOT/nodes/mother/lab/weyland-platform/k8s/open-webui/backup.yaml"
}

@test "the CronJob's embedded backup script is byte-identical to the repo" {
  run python3 - "$MANIFEST" "$REPO_ROOT/scripts/open_webui_backup.py" <<'PY'
import sys, yaml
cm = next(d for d in yaml.safe_load_all(open(sys.argv[1])) if d and d.get("kind") == "ConfigMap")["data"]
if cm.get("open_webui_backup.py") != open(sys.argv[2]).read():
    print("DRIFT open_webui_backup.py — run scripts/embed-open-webui-backup.sh"); sys.exit(1)
print("identical")
PY
  [ "$status" -eq 0 ]
  [[ "$output" == "identical" ]]
}

@test "the CronJob runs the embedded script against the data PVC and keeps 7" {
  run python3 - "$MANIFEST" <<'PY'
import sys, yaml
cj = next(d for d in yaml.safe_load_all(open(sys.argv[1])) if d and d.get("kind") == "CronJob")
spec = cj["spec"]["jobTemplate"]["spec"]["template"]["spec"]
c = spec["containers"][0]
claims = {v["name"]: v.get("persistentVolumeClaim", {}).get("claimName") for v in spec["volumes"]}
assert cj["spec"]["timeZone"] == "America/New_York", cj["spec"].get("timeZone")
assert c["command"] == ["python3", "/opt/backup/open_webui_backup.py", "/data", "/backup/open-webui", "7"], c["command"]
assert claims["data"] == "open-webui-data" and claims["backup"] == "open-webui-backup", claims
print("ok")
PY
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
}
