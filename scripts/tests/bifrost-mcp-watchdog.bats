#!/usr/bin/env bats
# B203 — the Bifrost MCP watchdog's decisions are covered in test_bifrost_mcp_health_check.py. This asserts the one
# thing pytest cannot: the CronJob runs the SAME script. Two copies of a watchdog drift silently on both sides;
# scripts/embed-bifrost-mcp-watchdog.sh regenerates the embedded copy.

setup() {
  load helper
}

@test "the CronJob's embedded watchdog is byte-identical to scripts/bifrost_mcp_health_check.py" {
  manifest="$REPO_ROOT/nodes/mother/lab/weyland-platform/k8s/bifrost/bifrost-mcp-watchdog.yaml"
  run python3 - "$manifest" "$REPO_ROOT/scripts/bifrost_mcp_health_check.py" <<'PY'
import sys, yaml
cm = next(d for d in yaml.safe_load_all(open(sys.argv[1])) if d and d.get("kind") == "ConfigMap")["data"]
if cm.get("bifrost_mcp_health_check.py") != open(sys.argv[2]).read():
    print("DRIFT — run scripts/embed-bifrost-mcp-watchdog.sh"); sys.exit(1)
print("identical")
PY
  [ "$status" -eq 0 ]
  [[ "$output" == "identical" ]]
}
