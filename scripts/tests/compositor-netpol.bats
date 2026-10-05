#!/usr/bin/env bats
# The compositors are locked to their front doors (2026-10-05, owner): NetworkPolicies, enforced by k3s's built-in
# controller. Before this any pod could call them directly — skipping the gateway's Keycloak identity check AND its
# mcp-gateway-audit line.
#   - weyland-mcp-compositor-memory (the shared agent memory): ONLY the MCP gateway (/mcp-memory, per-user identity).
#   - weyland-mcp-compositor (the read fleet): the MCP gateway (/mcp-fleet) + Bifrost (its `weyland_fleet` MCP client,
#     the coding agents' edge, gated by virtual keys) — Bifrost cannot present a 5-minute Keycloak token.
# A NetworkPolicy fails SILENTLY on a label typo (it then selects nothing, or locks the gateway out), so every label
# the policies select is cross-checked against the real Deployments' pod-template labels.

setup() {
  P="$BATS_TEST_DIRNAME/../../nodes/mother/lab/weyland-platform/k8s"
}

check() {
  python3 - "$P" "$@" <<'PY'
import sys, yaml, glob
p = sys.argv[1]
docs = [d for f in glob.glob(f"{p}/**/*.yaml", recursive=True) for d in yaml.safe_load_all(open(f)) if isinstance(d, dict)]
pols = {d["metadata"]["name"]: d for d in docs if d.get("kind") == "NetworkPolicy" and d["metadata"].get("namespace") == "weyland"}
deps = {d["metadata"]["name"]: d["spec"]["template"]["metadata"]["labels"] for d in docs
        if d.get("kind") == "Deployment" and d["metadata"].get("namespace") == "weyland"}
target, *allowed = sys.argv[2:]
name = f"{target}-front-door-only"
pol = pols.get(name)
assert pol, f"no NetworkPolicy {name}"
spec = pol["spec"]
assert spec["podSelector"]["matchLabels"] == {"app": target}, spec["podSelector"]
assert deps[target].get("app") == target, f"{target} Deployment pod label app={deps[target].get('app')}"
assert spec["policyTypes"] == ["Ingress"], f"policyTypes {spec['policyTypes']} — egress must stay open (rogueone, upstreams)"
(rule,) = spec["ingress"]
assert rule["ports"] == [{"protocol": "TCP", "port": 8000}], rule["ports"]
froms = sorted(f["podSelector"]["matchLabels"]["app"] for f in rule["from"])
assert froms == sorted(allowed), f"allowed {froms}, expected {sorted(allowed)}"
for a in allowed:
    assert deps.get(a, {}).get("app") == a, f"allowed source {a} has no Deployment with pod label app={a}"
for f in rule["from"]:
    assert set(f) == {"podSelector"}, f"a from-entry must be a same-namespace podSelector only: {f}"
print("ok")
PY
}

@test "the memory compositor admits ONLY the MCP gateway, on 8000" {
  run check weyland-mcp-compositor-memory weyland-mcp-gateway
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
}

@test "the fleet compositor admits the MCP gateway and Bifrost, on 8000" {
  run check weyland-mcp-compositor weyland-mcp-gateway bifrost
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
}
