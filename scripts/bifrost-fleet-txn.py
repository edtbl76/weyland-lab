"""The ship's end-to-end MCP transaction: one read-only fleet tool call THROUGH Bifrost (2026-10-16).

Why: agents reach the fleet as Bifrost -> weyland-mcp-compositor -> a backing server. A compositor ship restarts the
compositor, and Bifrost keeps the old pod's MCP session ("session terminated (404)", then "Missing session ID") until
Bifrost itself restarts. git-af3ae0c8 shipped green that way while every `weyland_fleet` call failed, because no ship
check went through Bifrost. This one does: initialize, tools/list (the key must see EXACTLY its one tool), tools/call.

  usage: python3 scripts/bifrost-fleet-txn.py [--env-file scripts/.env] [--url https://bifrost.weyland.lab/mcp]
  key:   BIFROST_SHIP_TXN_VK (the `ship-txn` virtual key, scoped by register_bifrost_vk_mcp.py to
         weyland_fleet k8s_namespaces_list only), from the environment or ONLY its line of --env-file
  out:   one line, TXN_OK (exit 0) or TXN_FAIL <reason> (exit 1). ship-images.sh reads the PRINTED verdict, like its
         other transactions; the exit code is for a hand run. A failure names the fix (rollout restart deploy/bifrost).
Stdlib only.
"""
import argparse
import json
import os
import sys
import urllib.request

URL = "https://bifrost.weyland.lab/mcp"
TOOL = "weyland_fleet-k8s_namespaces_list"
NAMESPACE = "weyland"
FIX = ("if Bifrost holds a stale session to a restarted compositor: kubectl -n weyland rollout restart deploy/bifrost "
       "(runbook mcp-gateway.md § Ship transaction key)")


def vk_from(env_file=None):
    """The key from the environment, else ONLY the BIFROST_SHIP_TXN_VK line of `env_file`; "" when absent."""
    key = os.environ.get("BIFROST_SHIP_TXN_VK", "").strip()
    if key or not env_file:
        return key
    try:
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                name, sep, value = line.strip().removeprefix("export ").partition("=")
                if sep and name.strip() == "BIFROST_SHIP_TXN_VK":
                    return value.strip().strip("'\"")
    except OSError:
        return ""
    return ""


def _post(url, body, key):
    """POST one JSON-RPC message; the parsed reply (JSON or the first SSE `data:` line), or {} for a 202/empty body."""
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={
        "Content-Type": "application/json", "Accept": "application/json, text/event-stream", "x-bf-vk": key})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read().decode(errors="replace")
    data = [line[5:].strip() for line in raw.splitlines() if line.startswith("data:")]
    text = data[0] if data else raw
    return json.loads(text) if text.strip() else {}


def _text(result):
    return " ".join(str(c.get("text", "")) for c in (result.get("content") or []) if isinstance(c, dict))


def verdict(listed, called):
    """TXN_OK only when the key sees exactly its one tool AND the call answered with the namespace."""
    tools = [x.get("name") for x in ((listed or {}).get("result") or {}).get("tools") or []]
    if tools != [TOOL]:
        return f"TXN_FAIL the ship-txn key must see exactly [{TOOL}], saw {tools} (re-run register_bifrost_vk_mcp.py)"
    if "error" in (called or {}):
        return f"TXN_FAIL {TOOL}: {str(called['error'].get('message'))[:160]} — {FIX}"
    result = (called or {}).get("result") or {}
    text = _text(result)
    if result.get("isError"):
        return f"TXN_FAIL {TOOL} errored: {text[:160]} — {FIX}"
    if NAMESPACE not in text.split():
        return f"TXN_FAIL {TOOL} answered without the {NAMESPACE} namespace: {text[:120]!r}"
    return "TXN_OK"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--env-file")
    ap.add_argument("--url", default=URL)
    args = ap.parse_args(argv)
    key = vk_from(args.env_file)
    if not key:
        print("TXN_FAIL no BIFROST_SHIP_TXN_VK (scripts/.env; runbook mcp-gateway.md § Ship transaction key)")
        return 1
    try:
        _post(args.url, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "ship-txn", "version": "1"}}}, key)
        _post(args.url, {"jsonrpc": "2.0", "method": "notifications/initialized"}, key)
        listed = _post(args.url, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, key)
        called = _post(args.url, {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
            "name": TOOL, "arguments": {"fieldSelector": f"metadata.name={NAMESPACE}"}}}, key)
    except (OSError, ValueError) as e:      # HTTPError and URLError are OSErrors; ValueError = an unparseable reply
        print(f"TXN_FAIL Bifrost {args.url}: {type(e).__name__} {str(e)[:120]} — {FIX}")
        return 1
    v = verdict(listed, called)
    print(v)
    return 0 if v == "TXN_OK" else 1


if __name__ == "__main__":
    sys.exit(main())
