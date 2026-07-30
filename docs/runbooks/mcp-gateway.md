# MCP Gateway — `weyland-mcp-gateway` (mesh / fleet governance)

The governed front door for the lab's MCP servers. It authenticates MCP callers (Keycloak) and injects a **verified
caller identity** downstream, which is what turns the audit-only ACT hook into an **enforcing** act policy gate. Two
edges make up the mesh-governance layer:

- **`weyland-mcp-gateway` = the server edge (inbound)** — this doc. Fronts the tool-server's `/mcp` + `/mcp-act`.
- **Bifrost = the agent edge (outbound)** — client-side MCP-*tool* aggregation for the agents (a later phase; **not**
  an LLM gateway — LLM routing stays MLflow + LiteLLM).

## Why a bespoke proxy (not FastMCP, not Prefect Horizon)
- **Prefect Horizon** — the obvious MCP-gateway product — is **managed SaaS/cloud** (servers run on `*.fastmcp.app`,
  mandatory internet + GitHub, no self-host). It would force exposing the air-gapped tool-server to the internet →
  rejected. It clashes with LAN-only / $0 / self-hosted.
- **FastMCP** (the self-hosted library Horizon is built on) is the right tool for *composing/remixing multiple* MCP
  servers, but its proxy middleware **can't inject a derived upstream header** — and injecting `X-Forwarded-Consumer`
  from the validated claim is the whole job here. So Phase 1 is a **thin auth reverse-proxy**
  (Starlette + httpx + PyJWT). FastMCP is held for when there are multiple MCP servers to compose.

## What it does (Phase 1)
`services/weyland-mcp-gateway/app.py` — three things, nothing more:
1. **Authenticate** — require a Keycloak Bearer JWT, validated against the realm JWKS (`JWTVerifier` equivalent:
   PyJWT + `PyJWKClient`). Un-authed → **401**.
2. **Inject the actor** — set `X-Forwarded-Consumer` = the token's `azp` claim (the agent's Keycloak `client_id`),
   **stripping** any client-supplied value (anti-spoof). The tool-server already reads that header into
   `guardrail_verdicts.actor` (the B14 seam), so verified identity flows downstream with **zero tool-server change**.
3. **Pass through** — stream the raw MCP Streamable-HTTP (JSON-RPC / SSE) to the backend `/mcp` (read) + `/mcp-act`
   (act) mounts.

**Gotcha — the header allowlist.** `fastapi-mcp` (0.4.0) forwards only an **allowlist** of headers from the MCP request
into each tool invocation (`FastApiMCP(app, headers=[...])`, default `['authorization']`). So the gateway-set
`x-forwarded-consumer` was silently dropped and `_actor` saw `None` (verdicts recorded NULL actor). Fix: both mounts
now pass `headers=["authorization", "x-forwarded-consumer"]` (`weyland-tool-server/main.py`).

## The enforcing act gate (Phase 2)
Now that a real `actor` arrives, the ACT hook gained `policy.gate` (`weyland-guard/guardrails/validators/policy.py`)
alongside the audit-only `policy.audit`. It **BLOCKs**:
- an act with **no actor** (a caller that bypassed the gateway),
- an actor **not in the allowlist**,
- a tool **not permitted** for that actor,
- an actor over its **per-minute rate cap**.

Policy is a small dict (`_DEFAULT_POLICY`, env-overridable JSON via `GUARD_ACT_POLICY`) — one entry per agent (per-agent
Keycloak clients → per-agent actors). **ENFORCING (`block`) live 2026-07-29** via `GUARDRAIL_MODE__policy__gate=block` on
the weyland-guard deployment — the operator now routes acts through the gateway (verified `weyland-operator` passes), so
unverified acts are denied for real. Toggle back to observe-only for a demo with the live `/admin/mode` toggle (Bearer)
rather than editing the manifest.

## Sequence (auth → actor → act gate)
```mermaid
sequenceDiagram
    participant A as Agent (operator)
    participant KC as Keycloak
    participant GW as MCP gateway
    participant TS as tool-server /mcp-act
    participant G as weyland-guard ACT hook
    A->>KC: client_credentials → token (azp = weyland-operator)
    A->>GW: MCP call + Authorization Bearer token
    GW->>GW: validate JWT (JWKS) ; extract azp
    GW->>TS: proxy + X-Forwarded-Consumer weyland-operator
    TS->>TS: fastapi-mcp forwards header → _actor
    TS->>G: POST /guard/act {tool, params, actor}
    G->>G: policy.gate — identity / allowlist / rate-limit
    G-->>TS: allow OR block
    TS-->>GW: tool result OR 403
    GW-->>A: result OR 403
```

## Deploy
- **Gateway** (built on rogueone like weyland-guard/agent): `docker build -t registry.weyland.lab/weyland-mcp-gateway:vN services/weyland-mcp-gateway && docker push …`; manifests `k8s/mcp-gateway/mcp-gateway.yaml` (Deployment + Service + Ingress `mcp.weyland.lab`, **not meshed** — plain HTTP to tool-server + Keycloak, no STRICT service in the path); Argo app `mcp-gateway` in `subdir-apps.yaml`.
- **Keycloak clients** (OpenTofu, `tofu/keycloak/mcp-agents.tf`) — one `service_accounts_enabled` (client_credentials) client per agent; `client_id` = the actor. Apply: `TF_VAR_operator_password=… tofu apply`. Secret via `tofu output -raw mcp_operator_client_secret`.
- **Act gate** rides the weyland-guard image (`policy.py` + the `x-forwarded-consumer` allowlist on the tool-server).
- **JWKS** is fetched from the in-cluster keycloak svc over HTTP (`http://keycloak.weyland.svc:8080/realms/weyland/…/certs`) — no CA trust needed; the token `iss` is still validated against `https://keycloak.weyland.lab/realms/weyland`.

## Verify
```
curl -sk https://mcp.weyland.lab/health                                   # ok
curl -sk -o /dev/null -w "%{http_code}\n" https://mcp.weyland.lab/mcp-act  # 401 (un-authed)
```
Mint an operator token (`client_credentials`) and drive a real MCP tool call through `mcp.weyland.lab/mcp` → confirm
the fresh verdicts carry `actor = weyland-operator`:
```
SELECT actor, validator, count(*) FROM guardrail_verdicts WHERE actor='weyland-operator' GROUP BY 1,2;
```
Act-gate enforcement (**live** via `GUARDRAIL_MODE__policy__gate=block` on the guard deployment; toggle to observe-only
for a demo via `/admin/mode`, Bearer `GUARD_ADMIN_TOKEN`): operator act → allow; NULL-actor → block
("no actor…"); unknown actor → block ("not in the act allowlist").

## Current state + loose ends
- Phase 1 (gateway + auth + actor) ✅ and Phase 2 (enforcing act gate) ✅ — both **proven + LIVE**; `policy.gate` is
  **enforcing (`block`)** as of 2026-07-29 (no-actor / unknown-actor / direct acts denied; `weyland-operator` via the gateway passes).
- ✅ **Operator wired** (2026-07-29) — `weyland-operator` mints a Keycloak `client_credentials` token and routes acts
  through the gateway (`act.py`; `OPERATOR_CLIENT_SECRET`), falling back to the direct path only if no secret is wired.
- **DNS:** `mcp.weyland.lab` is currently a client `/etc/hosts` stopgap — promote to CoreDNS + LAN DNS like the other
  subdomains ([[coredns-cluster-lan-resolution]]).
- **Coding agents** (opencode/Cline) may not send a Bearer on an MCP endpoint — they stay on the direct LAN path or go
  via Bifrost (agent edge) until they can auth.

Related: [runbooks/guardrails.md](guardrails.md) (the guard service + act gate), [runbooks/keycloak.md](keycloak.md),
[[keycloak-sso-b1.1]]. Design: `aidlc-docs/construction/mcp-gateway-design.md`.
