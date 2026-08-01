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
- **Gateway** (built on rogueone like weyland-guard/agent): `docker build -t registry.weyland.lab/weyland-mcp-gateway:vN services/weyland-mcp-gateway && docker push …`; manifests `k8s/mcp-gateway/mcp-gateway.yaml` (ServiceAccount `weyland-mcp-gateway` + Deployment + Service + Ingress `mcp.weyland.lab`, **meshed** — Istio sidecar + its own SA so the tool-server can authorize it by SPIFFE identity; stays PERMISSIVE so Traefik ingress still reaches it plaintext; gateway→tool-server + gateway→keycloak auto-mTLS); Argo app `mcp-gateway` in `subdir-apps.yaml`. Meshing was a **manifest-only** change (SA + `sidecar.istio.io/inject` label — no image rebuild).
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

## Anti-spoof — the act endpoints are gateway-only (Istio, 2026-07-29)
`policy.gate` blocks acts with no/unknown actor, but the tool-server trusts `X-Forwarded-Consumer` from any caller — so
a direct in-cluster POST to `/pipeline/trigger` with a forged `X-Forwarded-Consumer: weyland-operator` would still fire.
Closed by an Istio **`AuthorizationPolicy`** (`k8s/istio/authz-toolserver-act.yaml`, Argo app `istio-config` — **manual
sync**): a DENY rule scoped to the act paths (`/mcp-act*`, `/pipeline/trigger`, `/evals/run`, `/evals/score`), keyed on
`notPrincipals: [cluster.local/ns/weyland/sa/weyland-mcp-gateway]`. Any source that isn't the gateway SA — **including a
plaintext caller with no principal** — is denied at L7 before the app runs; read paths stay open. Requires the gateway
**meshed with its own SA** (both ends meshed → auto-mTLS carries the SPIFFE identity).

**Ordering:** mesh the gateway FIRST (auto-sync `mcp-gateway`), confirm it's up, THEN sync `istio-config` — if the policy
lands while the gateway is un-meshed (no principal) the gateway's own acts get denied too.

Verify (mother) — a forged direct act from a non-gateway pod is denied at L7 (`403 RBAC`), while the operator via the
gateway still `pass`es its `policy.gate`:
```
kubectl -n weyland exec deploy/weyland-guard -- python -c 'import httpx; print(httpx.post("http://weyland-tool-server.weyland.svc.cluster.local:8080/pipeline/trigger",json={"job_name":"weyland_eval_job"},headers={"X-Forwarded-Consumer":"weyland-operator"}).status_code)'   # 403 RBAC: access denied
```

## Bifrost — the agent edge (Phase 3b, `bifrost.weyland.lab`)
The **coding-agent** front door (`maximhq/bifrost`, `k8s/bifrost/`, Argo app `bifrost`). It connects to the compositor
as an upstream MCP server and re-exposes **all 91 fleet tools through one `/mcp`** endpoint — so a coding agent (Cline /
Cursor / Claude Code) points a single URL at the whole read-only lab. Reads only; **acts still go gateway → tool-server
`/mcp-act`** (Bifrost never touches the act lane). Two Traefik routers on the one host: `/` (UI) = Keycloak forward-auth;
`/mcp` = **not** forward-auth (MCP clients can't browser-SSO — the longer path outranks the UI router so agents skip SSO;
Bifrost's own virtual-key auth guards it, none enforced in-cluster = fine for LAN).

**Point a coding agent at it:** MCP endpoint `https://bifrost.weyland.lab/mcp` (streamable-HTTP). Mint a virtual key in
the UI (Virtual Keys) and grant it the `weyland_fleet` server for per-client tool scoping; the UI's **Connect agent**
button emits ready-to-paste client config.

**Re-add the upstream after a PVC loss** (config is currently UI-managed in the PVC — GitOps codification is `TODO(B111)`):
UI → **MCP Gateway → MCP Catalog → New MCP Server** → Name `weyland_fleet`, Connection Type **HTTP (Streamable)**,
Connection URL `http://weyland-mcp-compositor.weyland.svc.cluster.local:8000/mcp`, Auth Type **None** → Save. State goes
green and **Enabled Tools = 91/91**.

**Verify** the aggregated endpoint (external path through Traefik — proves the `/mcp` router bypasses forward-auth):
```
curl -sk -o /dev/null -w '%{http_code}\n' -X POST https://bifrost.weyland.lab/mcp -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"s","version":"0"}}}'   # 200 (not a 302/307 to Keycloak)
```
**B111** = adopt Bifrost's full agentic-gateway feature set (virtual keys, budgets, governance) — bake-off vs LiteLLM; that
work also does the config-as-GitOps (init-seed `config.json` + SealedSecret'd virtual keys, since the repo is public).

## Bifrost governance — budgets + key-sealing (B111, v1.6.7)

**Per-provider budget caps** (`scripts/register_bifrost_governance.py`, idempotent). v1.6.7 budgets are on a
**model-config** `(provider, model_name:"*", scope:"global")` via `POST /api/governance/model-configs` with nested
`budgets:[{max_limit, reset_duration:"1M"}]` — NOT on VKs (the VK-budget field in the getbifrost docs is a newer,
unreleased schema; v1.6.7 IS the latest release). `POST /api/governance/budgets` = 405 (read-only). 18 caps set:
Anthropic $20, others $10/mo. Verify: UI → Budgets & Limits, or `GET /api/governance/model-configs`.

**Key-sealing** — provider keys never sit as plaintext in the PVC. Flow:
```
scripts/seal_bifrost_keys.sh          # .env -> Secret (in memory) -> kubeseal -> writes the SealedSecret manifest
kubectl apply -f k8s/sealed-secrets/sealed/weyland__bifrost-provider-keys.yaml   # controller writes Secret bifrost-provider-keys
kubectl apply -f k8s/bifrost/bifrost.yaml                                        # adds envFrom
kubectl -n weyland rollout restart deploy/bifrost                               # REQUIRED — envFrom alone doesn't auto-roll
kubectl -n weyland exec -i deploy/weyland-guard -- python - < scripts/register_bifrost_providers.py            # add env.VAR keys
# ... smoke a few providers ...
kubectl -n weyland exec -i deploy/weyland-guard -- python - < scripts/register_bifrost_providers.py --purge    # drop plaintext
```
Result: every provider key is `type=env` (resolves from the SealedSecret'd pod env), **0 plaintext in the PVC**, API
shows keys redacted. Self-hosted (ollama/vllm/sgl) use dummy keys — not sealed. **GOTCHAS:** (1) adding `envFrom` did not
roll the pod → `rollout restart`. (2) env keys read back `type=env` + redacted value (not the literal `env.VAR`). (3)
**PUSH `bifrost.yaml` + the SealedSecret to git** — Argo selfHeal reverts a local-only envFrom → env empties → outage.
Restore-from-scratch: apply SealedSecret → restart → run `register_bifrost_providers.py`.

**Use-case routing does NOT live in Bifrost — it moved to LiteLLM (2026-07-31).** Bifrost OSS can't route/fail-over
well: **`chain_rule` is NOT on-failure fallback** (verified — a rule → down provider, vLLM off `502 connection refused`
= the documented trigger, with `chain_rule:true` + a second same-CEL rung did **not** cascade), and **adaptive
load-balancing** (weighted targets + capacity/error-aware failover) is **Enterprise-locked** (only static routing is OSS).
VK `provider_configs` auto-fallback IS OSS + transparent but can't resolve self-hosted (vllm/ollama) keys in v1.6.7.
So the 9 `wl-*` use-case aliases + fallback chains live in **LiteLLM** — see [runbooks/model-gateway.md](model-gateway.md)
(§ Use-case router). Bifrost keeps what it's good at OSS: the MCP agent edge, provider egress, budgets, key vault,
observability. `scripts/register_bifrost_routing.py` is **obsolete** (removed).

## Bifrost MCP library — durability + in-pod stdio runtime (B111)

The MCP clients Bifrost aggregates (`weyland_fleet` = the compositor, plus installed library servers) live in the **PVC**
(UI/API-added) — a wipe loses them. Codified for GitOps in **`scripts/register_bifrost_mcp_clients.py`** (idempotent) —
the durable source of truth. By auth type:
- **HTTP no-auth** — `weyland_fleet`, Context7, Excalidraw, Malwarebytes → reproduce fully (public URLs, no secrets).
- **HTTP OAuth** — Hugging Face, Linear → the script registers the *shell*; the OAuth grant is interactive, so after a
  restore **re-authorize each in the Bifrost UI** (they use dynamic client registration, so no app to pre-create — which
  is exactly why they installed and **GitHub didn't** — GitHub's remote MCP needs a manual `client_id` + Bifrost callback URL).
- **stdio** — Perplexity (`@perplexity-ai/mcp-server`), Playwright (`@playwright/mcp`) → run **in the Bifrost pod**.

**In-pod stdio runtime:** Bifrost is a Go binary on **Alpine, non-root, read-only `/usr`** — no node/npx/chromium, and a
runtime `apk add` is impossible. The **`mcp-runtime` initContainer** (`bifrost.yaml`) apk-installs node + chromium into a
shared `emptyDir`; Bifrost spawns the stdio servers off `PATH`/`LD_LIBRARY_PATH`. Same-Alpine-version chromium is
**musl-ABI compatible**, so Playwright drives the **system** chromium (`--executable-path /runtime/bin/chromium --no-sandbox`),
not its unsupported glibc download. Mem raised 512Mi→1.5Gi for headless chromium. The initContainer is **best-effort
(always exit 0)** so a failed apk/npm can't block Bifrost from booting. Perplexity inherits `PERPLEXITY_API_KEY` from the
pod env (`bifrost-provider-keys`).

**VK -> client scoping (durable, B111 2026-08-01):** a VK only serves the tools of the MCP clients *attached* to it, and
the governance **API cannot attach** runtime-registered clients (`PUT .../virtual-keys/{id}` with `mcp_configs` 500s
"failed to get MCP client: not found"). The attachment is a row in `governance_virtual_key_mcp_configs` (config.db),
keyed by the client's **integer PK**. Codified in **`scripts/attach_bifrost_vk_mcp.py`** — declarative scoping
(coding-agents -> fleet/Context7/HF/Linear/Perplexity/Playwright/GitHub; operator -> Excalidraw/Malwarebytes;
chat-eval -> none), resolved by client **name** (survives PVC-restore PK reassignment), idempotent + atomic. Runs IN the
bifrost pod (no system python/sqlite3 → use `/runtime/usr/bin/python3`, staged by the initContainer). A DB write alone
does nothing — the `/mcp` multiplexer builds its per-VK tool registry in memory at boot, so a **rollout restart is
required** for tools to flow. See memory `bifrost-vk-mcp-attach`.

**Restore-from-scratch (order matters):**
1. apply `bifrost.yaml` (initContainer stages the runtime)
2. `kubectl -n weyland exec -i deploy/weyland-guard -- python - < scripts/register_bifrost_mcp_clients.py`  (create clients)
3. `kubectl -n weyland exec -i deploy/bifrost -c bifrost -- /runtime/usr/bin/python3 - < scripts/attach_bifrost_vk_mcp.py`  (scope VKs)
4. `kubectl -n weyland rollout restart deploy/bifrost`  (reload — tools do NOT flow until this)
5. re-authorize Hugging_Face + Linear in the UI (OAuth grant is interactive).

**GITHUB (parked):** remote MCP has no DCR → make a GitHub App (read-only) → paste its `client_id` + Bifrost's OAuth callback URL.

## Current state + loose ends
- Phase 1 (gateway + auth + actor) ✅ and Phase 2 (enforcing act gate) ✅ — both **proven + LIVE**; `policy.gate` is
  **enforcing (`block`)** as of 2026-07-29 (no-actor / unknown-actor / direct acts denied; `weyland-operator` via the gateway passes).
- ✅ **Operator wired** (2026-07-29) — `weyland-operator` mints a Keycloak `client_credentials` token and routes acts
  through the gateway (`act.py`; `OPERATOR_CLIENT_SECRET`), falling back to the direct path only if no secret is wired.
- ✅ **Anti-spoof** (2026-07-29) — tool-server act endpoints locked to the gateway SA via an Istio `AuthorizationPolicy`;
  a forged direct act → `403 RBAC`. Gateway is now meshed with its own SA (see above).
- ✅ **DNS:** `mcp.weyland.lab` resolves via the LAN DNS **wildcard** (`weyland.lab → 192.168.1.243`, `k8s/coredns-lan.yaml`)
  — proven `dig +short mcp.weyland.lab @192.168.1.243 → 192.168.1.243`, identical to every Traefik-fronted subdomain
  (grafana/mlflow/…). No mcp-specific record is needed (it's on mother/Traefik, not a distinct IP like ollama/whisper).
  The `/etc/hosts` line on rogueone is that workstation's mechanism for **all** `*.weyland.lab` (its resolver is the FiOS
  router, not the LAN DNS) — not an mcp-specific stopgap ([[coredns-cluster-lan-resolution]]).
- ✅ **Bifrost agent edge** (Phase 3b, 2026-07-30) — `bifrost.weyland.lab` re-exposes all **91/91** fleet tools through
  one `/mcp`; external path verified `200`. Coding agents (Cline/Cursor/Claude Code) point one URL at the whole read-only
  lab. Image pinned to the multi-arch index digest (2026-07-30). Loose end: codify the MCP-upstream config as GitOps (`TODO(B111)`).

Related: [runbooks/guardrails.md](guardrails.md) (the guard service + act gate), [runbooks/keycloak.md](keycloak.md),
[[keycloak-sso-b1.1]]. Design: `aidlc-docs/construction/mcp-gateway-design.md`.
