#!/usr/bin/env python3
"""Idempotent Bifrost MCP-library client registration (B111) — GitOps durability for the MCP additions.

Bifrost stores its MCP clients in the PVC (UI/API-added), so a PVC wipe / restore loses them. This script re-registers
them from git — it is the durable source of truth. Run:
    kubectl -n weyland exec -i deploy/weyland-guard -- python - < scripts/register_bifrost_mcp_clients.py

Reproducibility by auth type:
- **HTTP no-auth** (weyland_fleet, Context7, Excalidraw, Malwarebytes): fully reproducible — public URLs, no secrets.
- **HTTP OAuth** (Hugging Face, Linear): the client SHELL is registered here; the OAuth GRANT is interactive. After a
  restore, **re-authorize each in the Bifrost UI** (auth_type=oauth uses dynamic client registration — no GitHub-style
  app to pre-create; that's why these two worked and GitHub didn't).
- **stdio** (Perplexity, Playwright): run IN the Bifrost pod off the node+chromium runtime that the `mcp-runtime`
  initContainer stages (see k8s/bifrost/bifrost.yaml). Perplexity inherits PERPLEXITY_API_KEY from the pod env
  (bifrost-provider-keys). Playwright drives Alpine's system chromium via --executable-path (musl-compatible).
  NOTE: the stdio commands may need a live tweak after the first roll (confirm npx resolution + Playwright flags);
  this file is the source of truth — fix here, re-run.
"""
import os, httpx

BASE = os.getenv("BIFROST_URL", "http://bifrost.weyland.svc.cluster.local:8080")

# (name, url, auth_type) — auth_type "oauth" registers the shell; re-authorize in the UI after a restore.
HTTP = [
    ("weyland_fleet", "http://weyland-mcp-compositor.weyland.svc.cluster.local:8000/mcp", "none"),
    ("Context7",      "https://mcp.context7.com/mcp",                                      "none"),
    ("Excalidraw",    "https://excalidraw-mcp-app.vercel.app/mcp",                         "none"),
    ("Malwarebytes",  "https://scamguard.malwarebytes.com/claude/mcp",                     "none"),
    ("Hugging_Face",  "https://huggingface.co/mcp",                                        "oauth"),
    ("Linear",        "https://mcp.linear.app/mcp",                                        "oauth"),
]

# (name, command, args, envs) — in-pod stdio off the mcp-runtime volume (node + system chromium).
# Use the DIRECT installed binaries (initContainer `npm install -g` → /runtime/usr/bin), NOT `npx`: npx re-fetches the
# package to its own cache on every spawn, which blows Bifrost's MCP init deadline ("context deadline exceeded").
STDIO = [
    ("Perplexity", "perplexity-mcp", [], ["PERPLEXITY_API_KEY"]),
    ("Playwright", "playwright-mcp", ["--headless", "--no-sandbox",
                                      "--browser", "chromium", "--executable-path", "/runtime/bin/chromium"], []),
]

c = httpx.Client(base_url=BASE, timeout=30)
existing = {cl["config"]["name"] for cl in (c.get("/api/mcp/clients").json().get("clients") or [])}

def create(name, body):
    if name in existing:
        print(f"{name:14} EXISTS"); return
    r = c.post("/api/mcp/client", json=body)   # create = /api/mcp/client (singular); /clients is GET-list only (405 on POST)
    ok = r.status_code < 300
    print(f"{name:14} {'CREATED' if ok else 'FAILED '} ({r.status_code}){'' if ok else ' ' + r.text[:140]}")

for name, url, auth in HTTP:
    create(name, {"name": name, "connection_type": "http",
                  "connection_string": {"value": url, "type": "plain_text"},
                  "auth_type": auth, "tools_to_execute": ["*"], "allow_on_all_virtual_keys": False})

for name, cmd, args, envs in STDIO:
    create(name, {"name": name, "connection_type": "stdio",
                  "stdio_config": {"command": cmd, "args": args, "envs": envs},
                  "auth_type": "none", "tools_to_execute": ["*"], "allow_on_all_virtual_keys": False})

print("\ndone. Post-restore: re-authorize Hugging_Face + Linear (OAuth) in the Bifrost UI; stdio (Perplexity/Playwright)"
      " need the mcp-runtime initContainer rolled (bifrost.yaml). tools_to_execute='*' is fine — Manual execution gates writes.")
