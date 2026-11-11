#!/usr/bin/env python3
"""Idempotent Bifrost MCP-library client registration (B111) — GitOps durability for the MCP additions.

Bifrost stores its MCP clients in the PVC (UI/API-added), so a PVC wipe / restore loses them. This script re-registers
them from git — it is the durable source of truth. Run:
    kubectl -n weyland exec -i deploy/weyland-guard -- python - < scripts/register_bifrost_mcp_clients.py

Reproducibility by auth type:
- **HTTP no-auth** (weyland_fleet, Context7, Excalidraw, Malwarebytes, Agent_Memory): fully reproducible — public or
  in-LAN URLs, no secrets.
- **HTTP OAuth** (Hugging Face, Linear, Jam, GitHub): the client SHELL is registered here with its `oauth_config`; the
  OAuth GRANT is interactive. Bifrost v2 rejects an OAuth client without `oauth_config` (400 "OAuth configuration is
  required when auth_type is 'oauth'", found 2026-11-11 registering Jam — Linear and Hugging Face had been created on an
  older Bifrost without one, so a restore from git would have failed for both until this fix). Hugging Face, Linear and
  Jam use dynamic client registration (no client id or secret anywhere); a create prints the authorize URL to open and
  the complete-oauth URL, and the Bifrost UI shows the same. GitHub's remote MCP has no DCR: it needs the GitHub OAuth
  app's client id in GITHUB_MCP_OAUTH_CLIENT_ID (the script says so instead of creating a broken client).
- **stdio** (Perplexity, Playwright): run IN the Bifrost pod off the node+chromium runtime that the `mcp-runtime`
  initContainer stages (see k8s/bifrost/bifrost.yaml). Perplexity inherits PERPLEXITY_API_KEY from the pod env
  (bifrost-provider-keys). Playwright drives Alpine's system chromium via --executable-path (musl-compatible).
  NOTE: the stdio commands may need a live tweak after the first roll (confirm npx resolution + Playwright flags);
  this file is the source of truth — fix here, re-run.

Exit 1 if any create fails, so a restore cannot report success with a client missing.
"""
import os
import sys

BASE = os.getenv("BIFROST_URL", "http://bifrost.weyland.svc.cluster.local:8080")

# OAuth settings per client, matching the live clients (read 2026-11-11). Scopes are the grant's ceiling.
OAUTH = {
    "Hugging_Face": {"registration_url": "https://huggingface.co/oauth/register",
                     "authorize_url": "https://huggingface.co/oauth/authorize",
                     "token_url": "https://huggingface.co/oauth/token", "resource": "https://huggingface.co/mcp",
                     "scopes": ["openid", "profile", "read-mcp", "read-repos", "jobs", "contribute-repos",
                                "inference-api"]},
    "Linear": {"registration_url": "https://mcp.linear.app/register", "authorize_url": "https://mcp.linear.app/authorize",
               "token_url": "https://mcp.linear.app/token", "resource": "https://mcp.linear.app/mcp",
               "scopes": ["read", "write"]},
    # B192 — Jam (jam.dev) UI-bug captures: DCR + PKCE, and the token is READ-scoped (`mcp:read`), so it cannot comment,
    # edit or delete whatever a key allows. Keys get only JAM_READ tools on top (register_bifrost_vk_mcp.py).
    "Jam": {"registration_url": "https://api.jam.dev/oauth/register", "authorize_url": "https://api.jam.dev/oauth/authorize",
            "token_url": "https://api.jam.dev/oauth/token", "resource": "https://mcp.jam.dev/mcp", "scopes": ["mcp:read"]},
    "GitHub_Remote": {"authorize_url": "https://github.com/login/oauth/authorize",
                      "token_url": "https://github.com/login/oauth/access_token",
                      "resource": "https://api.githubcopilot.com/mcp/",
                      "scopes": ["repo", "read:org", "read:user", "user:email", "read:packages", "write:packages",
                                 "read:project", "project", "gist", "notifications", "workflow", "codespace"],
                      "client_id_env": "GITHUB_MCP_OAUTH_CLIENT_ID"},
}

# (name, url, auth_type) — an "oauth" client takes its settings from OAUTH[name].
HTTP = [
    ("weyland_fleet", "http://weyland-mcp-compositor.weyland.svc.cluster.local:8000/mcp", "none"),
    ("Context7",      "https://mcp.context7.com/mcp",                                      "none"),
    ("Excalidraw",    "https://excalidraw-mcp-app.vercel.app/mcp",                         "none"),
    ("Malwarebytes",  "https://scamguard.malwarebytes.com/claude/mcp",                     "none"),
    ("Hugging_Face",  "https://huggingface.co/mcp",                                        "oauth"),
    ("Linear",        "https://mcp.linear.app/mcp",                                        "oauth"),
    ("GitHub_Remote", "https://api.githubcopilot.com/mcp/",                                "oauth"),
    ("Jam",           "https://mcp.jam.dev/mcp",                                           "oauth"),
    # B182 — shared agent memory: Basic Memory on rogueone (user unit basic-memory.service). No auth on the server;
    # rogueone's ufw admits ONLY mother (192.168.1.243) to :8765 — which is where Bifrost's pod traffic comes from.
    ("Agent_Memory",  "http://192.168.1.230:8765/mcp",                                     "none"),
]

# (name, command, args, envs) — in-pod stdio off the mcp-runtime volume (node + system chromium).
# PROVEN 2026-07-31: use the DIRECT installed binary (initContainer `npm install -g` → /runtime/usr/bin), NOT npx
# (npx re-fetches every spawn → blows the init deadline). AND the `envs` list MUST carry the node runtime vars —
# Bifrost spawns stdio servers with a STRIPPED env (only what's listed here), so without LD_LIBRARY_PATH/ICU_DATA
# node can't even load its shared libs and dies → "context deadline exceeded". Verified: Perplexity 4 tools, Playwright 24.
RUNTIME_ENVS = ["PATH", "LD_LIBRARY_PATH", "ICU_DATA", "HOME", "NODE_PATH"]
STDIO = [
    ("Perplexity", "perplexity-mcp", [], ["PERPLEXITY_API_KEY"] + RUNTIME_ENVS),
    ("Playwright", "playwright-mcp",
     ["--headless", "--no-sandbox", "--browser", "chromium", "--executable-path", "/runtime/bin/chromium"],
     RUNTIME_ENVS + ["PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD"]),
]


def oauth_config(settings):
    """Bifrost's `oauth_config` from our settings; None when a required client id is not in the environment."""
    cfg = {k: v for k, v in settings.items() if k != "client_id_env"}
    env = settings.get("client_id_env")
    if env:
        client_id = os.getenv(env, "")
        if not client_id:
            return None
        cfg["client_id"] = client_id
    return cfg


def http_body(name, url, auth):
    body = {"name": name, "connection_type": "http", "connection_string": {"value": url, "type": "plain_text"},
            "auth_type": auth, "tools_to_execute": ["*"], "allow_on_all_virtual_keys": False}
    if auth == "oauth":
        body["oauth_config"] = oauth_config(OAUTH[name])
    return body


def stdio_body(name, cmd, args, envs):
    return {"name": name, "connection_type": "stdio", "stdio_config": {"command": cmd, "args": args, "envs": envs},
            "auth_type": "none", "tools_to_execute": ["*"], "allow_on_all_virtual_keys": False}


def create(client, existing, name, body):
    """POST one client unless it exists. Returns (ok, report line)."""
    if name in existing:
        return True, f"{name:14} EXISTS"
    if body.get("auth_type") == "oauth" and not body.get("oauth_config"):
        env = OAUTH.get(name, {}).get("client_id_env", "?")
        return False, f"{name:14} NOT CREATED — set {env} (its OAuth app has no dynamic registration)"
    r = client.post("/api/mcp/client", json=body)   # PROVEN 2026-07-31: create = /api/mcp/client (singular). /clients = GET-list (405 on POST).
    if r.status_code >= 300:
        return False, f"{name:14} FAILED  ({r.status_code}) {r.text[:160]}"
    line = f"{name:14} CREATED ({r.status_code})"
    data = r.json() or {}
    if data.get("authorize_url"):
        line += f"\n{'':16}authorize: {data['authorize_url']}\n{'':16}then POST {data.get('complete_url', '(see the Bifrost UI)')}"
    return True, line


def main():
    import httpx

    headers = {"X-Bifrost-Setup-Token": os.environ["BIFROST_SETUP_TOKEN"]} if os.getenv("BIFROST_SETUP_TOKEN") else {}  # B202: v2.2.6+ setup lock (auth off)
    client = httpx.Client(base_url=BASE, timeout=30, headers=headers)
    existing = {cl["config"]["name"] for cl in (client.get("/api/mcp/clients").json().get("clients") or [])}
    rc = 0
    for name, url, auth in HTTP:
        ok, line = create(client, existing, name, http_body(name, url, auth))
        print(line)
        rc |= 0 if ok else 1
    for name, cmd, args, envs in STDIO:
        ok, line = create(client, existing, name, stdio_body(name, cmd, args, envs))
        print(line)
        rc |= 0 if ok else 1
    print("\ndone. Post-restore: authorize each OAuth client (Hugging_Face, Linear, Jam, GitHub_Remote) in the Bifrost UI;"
          " stdio (Perplexity/Playwright) need the mcp-runtime initContainer rolled (bifrost.yaml)."
          " tools_to_execute='*' here; each virtual key's tool list (register_bifrost_vk_mcp.py) is the real limit.")
    sys.exit(rc)


if __name__ == "__main__":
    main()
