"""Summarize one headless trial run from its stream-json log: the init event (plugins, MCP servers, model, tools), the
result event (subtype, turns, cost, usage) and, optionally, the final result text.
usage: read_run.py <run.jsonl> [--text]"""
import json
import sys

init = result = None
asks = 0
for line in open(sys.argv[1]):
    try:
        e = json.loads(line)
    except ValueError:
        continue
    if e.get("type") == "system" and e.get("subtype") == "init":
        init = e
    elif e.get("type") == "result":
        result = e
    elif e.get("type") == "assistant":
        for c in (e.get("message") or {}).get("content") or []:
            if c.get("type") == "tool_use" and c.get("name") == "AskUserQuestion":
                asks += 1
if init is None or result is None:
    sys.exit(f"incomplete run log: init={init is not None} result={result is not None}")
print("model:", init.get("model"), "| plugins:", init.get("plugins"), "| mcp:", init.get("mcp_servers"),
      "| plugin_errors:", init.get("plugin_errors"), "| mcp_errors:", init.get("mcp_server_errors"))
u = result.get("usage") or {}
print("result:", result.get("subtype"), "| is_error:", result.get("is_error"), "| turns:", result.get("num_turns"),
      "| duration_s:", round((result.get("duration_ms") or 0) / 1000), "| cost_usd_equiv:", result.get("total_cost_usd"),
      "| in/out/cache_r/cache_w:", u.get("input_tokens"), u.get("output_tokens"), u.get("cache_read_input_tokens"),
      u.get("cache_creation_input_tokens"), "| AskUserQuestion calls:", asks)
if "--text" in sys.argv:
    print(result.get("result", "")[:3000])
