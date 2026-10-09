#!/usr/bin/env python3
"""Virtual-key → MCP-client scoping through Bifrost's API (B203) — GitOps-durable source of truth.

Replaces `attach_bifrost_vk_mcp.py`, which wrote `config.db` directly and then needed a Bifrost restart because the
v1.6.7 API could not attach a runtime-registered client ("failed to get MCP client: not found"). On v2.2.6,
`PUT /api/governance/virtual-keys/{id}` takes `mcp_configs: [{mcp_client_name, tools_to_execute}]`, resolves the client
by NAME and reloads the key in memory, so the change applies live (proven 2026-10-09 on a throwaway key: `/mcp` went
0 → 2 → 0 tools with no restart). Run:
    kubectl -n weyland exec -i deploy/weyland-guard -- env BIFROST_URL=http://bifrost.weyland.svc.cluster.local:8080 python - < scripts/register_bifrost_vk_mcp.py

`SCOPING` below is the source of truth (scope by USE, not per agent): coding agents get the dev/coding tool surface,
the operator gets drawing/security plus read-only shared memory, chat-eval stays toolless. Keys not named here (e.g.
`realm-llm`) are never touched. Per key it compares the live grants with the desired set and PUTs only on a difference;
a PUT carries the key's WHOLE set (Bifrost replaces it; existing rows keep their ids), then the key is read back.
Fails (exit 1) on a missing key, a desired client that is not registered (run register_bifrost_mcp_clients.py first —
never drop a grant silently), a rejected PUT or a read-back that does not match. Runbook: docs/runbooks/mcp-gateway.md.
"""
import os
import sys

BASE_ENV = "BIFROST_URL"   # required, passed by the runbook command; no default, so a missing URL fails loudly
# B182 (2026-10-03): Agent_Memory — coding agents read AND write the shared memory; the operator only recalls.
MEMORY_READ = ["search_notes", "read_note", "view_note", "read_content", "build_context", "recent_activity",
               "list_directory", "search", "fetch"]
# VK name -> the MCP clients (by name) it may use. An entry is a client name (all its tools) or (name, [tools]).
SCOPING = {
    "coding-agents": ["weyland_fleet", "Context7", "Hugging_Face", "Linear", "Perplexity", "Playwright", "GitHub_Remote",
                      "Agent_Memory"],
    "operator":      ["Excalidraw", "Malwarebytes", ("Agent_Memory", MEMORY_READ)],
    "chat-eval":     [],   # explicitly toolless
}
ALL_TOOLS = ["*"]


def _get(client, path, key):
    resp = client.get(path, params={"limit": 1000})
    if resp.status_code != 200:
        raise SystemExit(f"GET {path} {resp.status_code} (is BIFROST_SETUP_TOKEN set?): {resp.text[:200]}")
    body = resp.json()
    rows = body.get(key) or []
    if body.get("total_count", len(rows)) > len(rows):
        raise SystemExit(f"GET {path} returned {len(rows)} of {body.get('total_count')} — refusing a partial reconcile")
    return rows


def desired(vk_name: str) -> dict:
    """{client name: sorted tools} for one key."""
    out = {}
    for entry in SCOPING[vk_name]:
        name, tools = (entry, ALL_TOOLS) if isinstance(entry, str) else entry
        out[name] = sorted(tools)
    return out


def live(vk: dict) -> dict:
    return {(c.get("mcp_client") or {}).get("name"): sorted(c.get("tools_to_execute") or [])
            for c in vk.get("mcp_configs") or []}


def _body(vk: dict, want: dict) -> dict:
    row_ids = {(c.get("mcp_client") or {}).get("name"): c.get("id") for c in vk.get("mcp_configs") or []}
    configs = []
    for entry in SCOPING[vk["name"]]:
        name = entry if isinstance(entry, str) else entry[0]
        cfg = {"mcp_client_name": name, "tools_to_execute": want[name]}
        if row_ids.get(name) is not None:
            cfg["id"] = row_ids[name]
        configs.append(cfg)
    return {"mcp_configs": configs}


def reconcile(client):
    """Return (report lines, exit code)."""
    registered = {(c.get("config") or {}).get("name") for c in _get(client, "/api/mcp/clients", "clients")}
    keys = {v.get("name"): v for v in _get(client, "/api/governance/virtual-keys", "virtual_keys")}
    lines, rc = [], 0
    for vk_name in SCOPING:
        vk = keys.get(vk_name)
        if vk is None:
            lines.append(f"{vk_name}: MISSING — no such virtual key"); rc = 1; continue
        want = desired(vk_name)
        unregistered = sorted(n for n in want if n not in registered)
        if unregistered:
            lines.append(f"{vk_name}: NOT WRITTEN — client(s) not registered: {', '.join(unregistered)} "
                         "(run register_bifrost_mcp_clients.py first)"); rc = 1; continue
        if live(vk) == want:
            lines.append(f"{vk_name}: unchanged ({len(want)} client(s))"); continue
        resp = client.put(f"/api/governance/virtual-keys/{vk['id']}", json=_body(vk, want))
        if resp.status_code >= 300:
            lines.append(f"{vk_name}: PUT {resp.status_code} {resp.text[:200]}"); rc = 1; continue
        after = {v.get("name"): v for v in _get(client, "/api/governance/virtual-keys", "virtual_keys")}.get(vk_name)
        if after is None or live(after) != want:
            lines.append(f"{vk_name}: read-back mismatch — stored {live(after or {})}"); rc = 1; continue
        lines.append(f"{vk_name}: updated → {', '.join(want) or '(no clients)'}")
    return lines, rc


def main():
    base = os.getenv(BASE_ENV) or ""
    if not base:
        raise SystemExit(f"{BASE_ENV} is not set (see the run command in this script's docstring)")
    import httpx

    headers = {"X-Bifrost-Setup-Token": os.environ["BIFROST_SETUP_TOKEN"]} if os.getenv("BIFROST_SETUP_TOKEN") else {}  # B202: v2.2.6+ setup lock (auth off)
    with httpx.Client(base_url=base, timeout=30, headers=headers) as client:
        lines, rc = reconcile(client)
    print("\n".join(lines))
    sys.exit(rc)


if __name__ == "__main__":
    main()
