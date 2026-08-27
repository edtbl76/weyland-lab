# MCP Gateway — design (B19, the MCP-gateway half of B17+B19)

## Goal
Stand up a **self-hosted MCP gateway** — the governed front door for the lab's MCP servers — so that (1) MCP traffic is
**authenticated** (Keycloak) instead of open-on-LAN, and (2) the authenticated caller identity flows downstream as the
**`actor`**, which **unblocks the enforcing act policy gate** (the ACT-hook allowlist/rate-limit/block that's been parked
waiting for a real caller identity).

Three-lane split, no overlap:
- **FastMCP** = INBOUND / server edge — **this doc**. Fronts our MCP servers.
- **Bifrost** = OUTBOUND / agent edge — MCP-*tool* aggregation for agents (Phase 3, own design). **NOT** an LLM gateway.
- **LLM routing** stays the MLflow AI Gateway (B100) + LiteLLM (B26).

## Why not Prefect Horizon
Horizon (the obvious name — Prefect's MCP platform) is **managed SaaS/cloud**: servers run on `*.fastmcp.app`, mandatory
internet + GitHub, no self-host. It would force exposing the air-gapped tool-server to the internet → **rejected**.
**FastMCP** (Apache-2.0, `pip install fastmcp`) is the self-hosted library Horizon is built on and does the job on-LAN.

## Architecture (Phase 1)
```
agent (operator B66 / weyland-agent / coding agents)
  │  Authorization: Bearer <keycloak-token>
  ▼
FastMCP gateway   (mcp.weyland.lab · new k8s pod, ns weyland)
  │  1. validate token   (Keycloak JWKS)
  │  2. extract caller claim → set X-Forwarded-Consumer
  │  3. proxy to the backend MCP mount
  ▼
weyland-tool-server   /mcp (read)   +   /mcp-act (act)
  │  _actor reads X-Forwarded-Consumer → guardrail_verdicts.actor  (existing B14 seam, no change)
  ▼
weyland-guard   (ACT hook: policy.audit shadow → ENFORCING = Phase 2)
```
FastMCP composition: `FastMCP.as_proxy(ProxyClient("http://weyland-tool-server.weyland.svc:<port>/mcp"))` (and
`/mcp-act`), exposed as one authenticated HTTP endpoint at `mcp.weyland.lab`.

## Implementation pivot (2026-07-29): thin auth-proxy, not FastMCP (for Phase 1)
FastMCP was the named pick, but on build its **proxy middleware cannot inject a *derived* upstream header** — it reads
the caller token (`get_http_headers()`) but has *"no mechanism for setting HTTP headers on requests forwarded to backend
MCP servers"* (only tool-arg/result/state mutation). The whole job here is to **set `X-Forwarded-Consumer` from the
validated claim**, so FastMCP is the wrong shape for a single-backend auth-gating proxy. **Phase 1 = a thin auth
reverse-proxy** (Starlette + httpx + PyJWT-against-Keycloak-JWKS). **FastMCP is retained for later multi-server
composition / tool-level RBAC / remix** — which only becomes relevant once there are *multiple* MCP servers to compose
(Home Assistant, Spotify, etc.). Same architecture as above; only the library changes.

## Key decisions (with recommendations)
1. **Auth = Keycloak bearer, validated AT the gateway — not forward-auth.** MCP callers are AGENTS (programmatic), so the
   browser-redirect forward-auth used for the lab UIs doesn't fit. The gateway validates Keycloak-issued JWTs directly.
   **Pick: FastMCP `JWTVerifier`** against Keycloak's JWKS (`…/realms/weyland/protocol/openid-connect/certs`) — simpler
   than full `RemoteAuthProvider`/DCR for machine clients. Revisit RemoteAuthProvider only if we want DCR.
2. **Agents get tokens via Keycloak `client_credentials`.** Each agent = a confidential Keycloak client; it fetches a
   token and presents `Authorization: Bearer` to the gateway. This is the change on the *agent* side (they call
   `mcp.weyland.lab` with a token instead of the open tool-server URL).
3. **Actor = the token's `azp` / `preferred_username` claim → `X-Forwarded-Consumer`.** The tool-server ALREADY reads
   that header into `guardrail_verdicts.actor` (B14 anti-spoof seam) — **zero tool-server change**.
4. **Deployment:** new pod `weyland-mcp-gateway` (ns `weyland`), ClusterIP + Traefik ingress `mcp.weyland.lab` (wildcard
   TLS), Argo-managed. **Not meshed** — it talks plain HTTP to the tool-server + JWKS to Keycloak, no STRICT-mTLS service
   in the path (mirrors the registry). Small Python image (`pip install fastmcp`).
5. **Scope boundary:** Phase 1 delivers **auth + actor**. **Phase 2** (enforcing act gate in weyland-guard) rides on the
   verified actor and is a follow-on, not this phase.

## Components to build (Phase 1)
- `services/weyland-mcp-gateway/` — `app.py` (FastMCP proxy + JWTVerifier), `Dockerfile`.
- `k8s/mcp-gateway/` — deployment + service + ingress (+ Argo app entry in `subdir-apps.yaml`).
- **Keycloak** — a resource/audience client for the gateway + agent client(s) for `client_credentials`.
- **Agent-side** — point the operator / weyland-agent / coding-agent MCP config at `mcp.weyland.lab` with a token.
- **Docs** — `docs/runbooks/mcp-gateway.md` + `mcp.weyland.lab` into `api.md` / `hosts.md` / `arch.md` + CoreDNS/etc.

## Open questions (confirm at build)
- **Keycloak client model:** one shared "agents" client vs **per-agent** clients. → recommend **per-agent** so the
  `actor` is meaningful (operator vs weyland-agent vs coding-agent), which is the whole point of injecting it.
- **FastMCP proxy preserves the `/mcp` vs `/mcp-act` split** (two mounts, kept distinct so the act gate applies only to
  `/mcp-act`) — verify it doesn't collapse them.
- **Coding agents (opencode / Cline) MCP auth** — do they support a custom `Authorization` header on an MCP endpoint?
  The operator + weyland-agent are ours (easy); third-party clients may not. Verify per client; if not, they stay on the
  direct (LAN-only, un-gated) path until they can auth, or go via Bifrost (Phase 3).

## Phasing
- **P1 (this doc):** FastMCP gateway + Keycloak auth + actor forwarding. Done-when: a token'd call through
  `mcp.weyland.lab` lands the right `actor` in `guardrail_verdicts`.
- **P2:** enforcing act policy gate in weyland-guard (allowlist/rate-limit/`block` on the ACT hook, keyed on the now-real
  actor) — the `policy.audit` shadow validator promoted to enforcing.
- **P3:** Bifrost (client-side MCP-tool aggregation) — own design.
- **Later:** B17 A2A eval.
