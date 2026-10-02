#!/usr/bin/env bats
# Guards the assumption LiteLLMSpendObserved is built on (2026-10-02): in LiteLLM's model_list, a route whose model has
# the `openai/` prefix is ALWAYS the hop to Bifrost (api_base = the in-cluster Bifrost /v1). The alert excludes
# api_provider="openai" because Bifrost already counts that money; a direct OpenAI route (or an openai/ route to any
# other host) would be paid spend that NEITHER spend alert sees. Fails closed: a config with no openai/ routes, or one
# that will not parse, is a broken guard, not a pass.

setup() {
  CONFIG="${BATS_TEST_DIRNAME}/../../nodes/mother/lab/weyland-platform/k8s/litellm/configmap.yaml"
  T="$(mktemp -d)"
}
teardown() { rm -rf "$T"; }

# check_routes <configmap.yaml> — exit 0 all openai/ routes go to Bifrost · 1 a violation · 2 cannot check
check_routes() {
  python3 - "$1" <<'PY'
import sys, yaml
BIFROST = "http://bifrost.weyland.svc.cluster.local:8080/v1"
try:
    cm = yaml.safe_load(open(sys.argv[1]))
    routes = yaml.safe_load(cm["data"]["config.yaml"])["model_list"]
except Exception as exc:
    print(f"cannot read the LiteLLM model_list: {exc}"); sys.exit(2)
hops = [r for r in routes if str(r.get("litellm_params", {}).get("model", "")).startswith("openai/")]
if not hops:
    print("no openai/ routes found — guard is checking nothing"); sys.exit(2)
bad = [r["model_name"] for r in hops if r["litellm_params"].get("api_base") != BIFROST]
if bad:
    print(f"openai/ route(s) not pointed at Bifrost: {bad}"); sys.exit(1)
print(f"OK — {len(hops)} openai/ route(s), all via Bifrost")
PY
}

@test "every openai/ LiteLLM route goes to Bifrost (the spend-alert partition holds)" {
  run check_routes "$CONFIG"
  [ "$status" -eq 0 ] && [[ "$output" == OK* ]] || { echo "$output"; return 1; }
}

@test "a direct openai/ route is caught (the guard is not vacuous)" {
  cat > "$T/cm.yaml" <<'EOF'
data:
  config.yaml: |
    model_list:
      - model_name: wl-agentic
        litellm_params: {model: openai/anthropic/claude-haiku-4-5, api_base: "http://bifrost.weyland.svc.cluster.local:8080/v1"}
      - model_name: sneaky
        litellm_params: {model: openai/gpt-4o, api_key: os.environ/OPENAI_API_KEY}
EOF
  run check_routes "$T/cm.yaml"
  [ "$status" -eq 1 ] && [[ "$output" == *"['sneaky']"* ]] || { echo "status=$status $output"; return 1; }
}

@test "a config it cannot read is a broken guard, not a pass" {
  echo "data: {}" > "$T/cm.yaml"
  run check_routes "$T/cm.yaml"
  [ "$status" -eq 2 ] && [[ "$output" == *"cannot read"* ]] || { echo "status=$status $output"; return 1; }
}
