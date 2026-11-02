#!/usr/bin/env bats
# Follow-on brownfield judge: the new host + third private lane. Exit codes and config facts only.
# Run with the round-1 judge alongside: TRIAL=<repo> bats judge.bats judge2.bats

setup() {
  CHECK="$TRIAL/scripts/check-private-lanes.py"
  CONFIG="$TRIAL/nodes/mother/lab/weyland-platform/k8s/litellm/configmap.yaml"
  FX="$BATS_TEST_DIRNAME"
}

expect() {
  [ -f "$CHECK" ] || { echo "no guard at $CHECK"; return 1; }
  run python3 "$CHECK" "$2"
  if [ "$status" -ne "$1" ]; then
    echo "want exit $1, got $status: $output"
    return 1
  fi
}

@test "follow-on: a private alias on the new host 192.168.1.231 passes (0)" {
  expect 0 "$FX/ok-231.yaml"
}

@test "follow-on: a host that is still not allowed (192.168.1.232) is caught (1)" {
  expect 1 "$FX/off-232.yaml"
}

@test "follow-on: the real config has wl-private-fast on both hosts and the rag -> fast fallback" {
  python3 -c '
import sys, yaml
c = yaml.safe_load(yaml.safe_load(open(sys.argv[1]))["data"]["config.yaml"])
hosts = {m["litellm_params"].get("api_base", "") for m in c["model_list"] if m["model_name"] == "wl-private-fast"}
want = {"http://192.168.1.230:11434", "http://192.168.1.231:11434"}
fb = [r for s in ("router_settings", "litellm_settings") for r in ((c.get(s) or {}).get("fallbacks") or [])]
ok_fb = any("wl-private-fast" in (r.get("wl-private-rag") or []) for r in fb)
print("fast hosts:", sorted(hosts), "| rag->fast:", ok_fb)
sys.exit(0 if want <= {h.rstrip("/") for h in hosts} and ok_fb else 1)' "$CONFIG"
}
