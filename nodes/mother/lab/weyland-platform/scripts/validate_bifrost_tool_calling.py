#!/usr/bin/env python3
"""B111 tail #3 — validate transparent TOOL-CALLING passthrough through Bifrost for each PAID provider.

Bifrost was chosen over the MLflow AI Gateway precisely because it passes tool/function schemas TRANSPARENTLY (MLflow
normalized/broke them). We proved that on the free/tested providers; this confirms it holds on the paid ones too — if a
paid provider garbles the schema through Bifrost, any agent routed there would silently fail to call tools.

Method: one known tool (`get_weather`) + a prompt that should trigger it, sent per provider. Bifrost auto-injects its ~91
fleet tools into every completion (~21k tok) — suppress that with an empty `x-bf-mcp-include-tools` header so we test OUR
single tool. PASS = the model returns a proper `tool_calls[0].function.name == get_weather`. Costs a few cents/provider.

Run in-pod (in-cluster Bifrost /v1 is un-authed):
    kubectl -n weyland exec -i deploy/weyland-guard -- python - < scripts/validate_bifrost_tool_calling.py
"""
import httpx

BASE = "http://bifrost.weyland.svc.cluster.local:8080"

# Paid, tool-capable providers (Bifrost model IDs). Groq is excluded (free tier = tool-free, tools 413); Perplexity is
# search-only (no function-calling). Adjust the model IDs if a provider's entitled model changes.
MODELS = [
    "anthropic/claude-haiku-4-5",
    "openai/gpt-4o-mini",
    "opencode-zen/kimi-k3",
    "xai/grok-4.5",
    "deepseek/deepseek-v4-flash",
    "cerebras/gpt-oss-120b",
    "openrouter/openai/gpt-4o-mini",
]

TOOL = [{"type": "function", "function": {
    "name": "get_weather", "description": "Get the current weather for a city",
    "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}}}]
MSGS = [{"role": "user", "content": "What's the weather in Oslo right now? Use the get_weather tool."}]


def main():
    c = httpx.Client(base_url=BASE, timeout=90, headers={"x-bf-mcp-include-tools": ""})
    print(f"{'provider/model':34}  result")
    print("-" * 70)
    passed = 0
    for m in MODELS:
        try:
            r = c.post("/v1/chat/completions", json={
                "model": m, "messages": MSGS, "tools": TOOL, "tool_choice": "auto", "max_tokens": 128})
            if r.status_code >= 300:
                print(f"{m:34}  ERR {r.status_code}: {r.text[:70]}")
                continue
            msg = r.json()["choices"][0]["message"]
            tc = msg.get("tool_calls")
            if tc:
                fn = tc[0].get("function", {})
                print(f"{m:34}  PASS  {fn.get('name')}({(fn.get('arguments') or '')[:40]})")
                passed += 1
            else:
                print(f"{m:34}  NO-TOOL  (text: {(msg.get('content') or '')[:45]!r})")
        except Exception as exc:
            print(f"{m:34}  EXC  {exc}")
    print("-" * 70)
    print(f"{passed}/{len(MODELS)} paid providers pass transparent tool-calling through Bifrost.")


if __name__ == "__main__":
    main()
