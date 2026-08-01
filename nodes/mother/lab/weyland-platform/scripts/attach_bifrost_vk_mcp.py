#!/usr/bin/env python3
"""Idempotent Bifrost VK->MCP-client attachment (B111) — GitOps durability for the virtual-key tool scoping.

WHY THIS IS A DIRECT DB WRITE (not the API): Bifrost's governance API cannot attach a runtime-registered MCP client to
a virtual key — `PUT /api/governance/virtual-keys/{id}` with `mcp_configs` 500s "failed to get MCP client: not found"
for every reference form (UUID client_id, name, integer PK). The attachment lives in the `governance_virtual_key_mcp_configs`
join table (config.db, SQLite in the PVC), keyed by `mcp_client_id` = the INTEGER autoincrement PK of `config_mcp_clients`.
This script resolves that mapping by client NAME (so it survives a PVC restore where the integer PKs are reassigned) and
writes the join rows directly. See docs/runbooks/mcp-gateway.md and the memory bifrost-vk-mcp-attach.

RESTORE ORDER (after a PVC wipe):
  1. register_bifrost_mcp_clients.py  — re-create the MCP clients (API, run in weyland-guard).
  2. THIS script                      — re-attach clients to VKs (DB, run IN the bifrost pod).
  3. rollout restart deploy/bifrost   — REQUIRED: the /mcp multiplexer builds its per-VK tool registry in memory at
                                        boot; the governance READ path reflects the DB live, but tools do NOT flow
                                        until the process reloads. A DB write alone does nothing to the running server.

RUN (bifrost has no system python/sqlite3 CLI — use the mcp-runtime-staged python, and -i to pipe stdin):
    kubectl -n weyland exec -i deploy/bifrost -c bifrost -- /runtime/usr/bin/python3 - < scripts/attach_bifrost_vk_mcp.py
    kubectl -n weyland rollout restart deploy/bifrost      # then this

The scoping below is the SOURCE OF TRUTH (scope by USE, not per-agent): coding agents get the dev/coding tool surface,
the operator gets the drawing/security surface, chat-eval stays toolless. Edit here + re-run to change scoping.
"""
import sqlite3, json, sys

DB = "/app/data/config.db"

# VK name -> the MCP clients (by name) attached to it. Names must match config_mcp_clients.name exactly.
SCOPING = {
    "coding-agents": ["weyland_fleet", "Context7", "Hugging_Face", "Linear", "Perplexity", "Playwright", "GitHub_Remote"],
    "operator":      ["Excalidraw", "Malwarebytes"],
    "chat-eval":     [],   # explicitly toolless
}
TOOLS = json.dumps(["*"])   # tools_to_execute — all tools of each attached client

con = sqlite3.connect(DB, timeout=30)
cur = con.cursor()
client_id = {name: cid for cid, name in cur.execute("select id, name from config_mcp_clients")}
vk_id = {name: vid for vid, name in cur.execute("select id, name from governance_virtual_keys")}

changed = 0
for vk_name, client_names in SCOPING.items():
    if vk_name not in vk_id:
        print(f"WARN  vk '{vk_name}' not found — skipping", file=sys.stderr); continue
    vid = vk_id[vk_name]
    cur.execute("delete from governance_virtual_key_mcp_configs where virtual_key_id=?", (vid,))
    for cname in client_names:
        cid = client_id.get(cname)
        if cid is None:
            print(f"WARN  client '{cname}' not found (register it first) — skipping for {vk_name}", file=sys.stderr); continue
        cur.execute(
            "insert into governance_virtual_key_mcp_configs (virtual_key_id, mcp_client_id, tools_to_execute) values (?,?,?)",
            (vid, cid, TOOLS))
        changed += 1
con.commit()

print("attached VK -> clients:")
for vk_name, mcid, cname in cur.execute(
        "select v.name, m.mcp_client_id, c.name from governance_virtual_key_mcp_configs m "
        "join governance_virtual_keys v on v.id=m.virtual_key_id "
        "join config_mcp_clients c on c.id=m.mcp_client_id order by v.name, m.mcp_client_id"):
    print(f"  {vk_name:14} -> {cname} (client#{mcid})")
print(f"\n{changed} rows written. NOW: kubectl -n weyland rollout restart deploy/bifrost  (tools do NOT flow until reload).")
