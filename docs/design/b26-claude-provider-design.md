# B26 — Hermes brain: add Claude (Anthropic) provider — gated design

**Status:** DESIGN (not started). Supersedes the one-paragraph backlog sketch.
**Depends on:** B2 (Hermes live, CT 104), B5 (Prometheus/Grafana/Alertmanager + Telegram alert path).
**Feeds / pairs with:** B17+B19 (MCP/egress gateway — this proxy is a first instance of that governance chokepoint).

## Roadmap fit — this introduces the long-planned LLM gateway

LiteLLM was in the **original architecture** (`aidlc-docs/inception/requirements-analysis.md` — "→ LiteLLM
(future)", alongside the tool server / Dagster / vLLM) as a unified model-serving front for operators, then
deferred out of Iteration-0 scope. It was never given its own backlog number. **B26 is the concrete first
use case that stands it up.** Implication: **deploy it as the general gateway, not a single-purpose Claude
shim** — a `weyland`-ns LiteLLM that today fronts one Anthropic route, but is configured so it can later (a)
front Ollama (CT 102) and vLLM (future, rogueone) behind one OpenAI-compatible surface, (b) carry per-key
budgets/rate-limits for every consumer (Hermes, OpenClaw, Open WebUI, opencode/Cline B15), and (c) become the
LLM half of the B17+B19 gateway. Scope *this* unit to the Claude egress + gating + observability path only —
but don't make deployment choices (naming, Secret layout, route config) that would block that growth.

---

## Goal

Give Hermes a **deliberately-invoked, human-gated** second brain — the Anthropic Claude API — for the
handful of hard reasoning/coding turns the local `qwen3-coder:30b` fumbles. Local stays the everyday
brain; Claude is break-glass escalation, **never** background plumbing.

## Hard requirements (from the operator)

1. **No automatic off-LAN calls — ever — unless explicitly enabled.** Main turns and *every* background
   lane must stay local by default.
2. **Observable:** when the off-LAN path is enabled and/or used, emit a signal into Prometheus that
   Alertmanager routes to Telegram (reuse B5 Phase 2a — `@weyland_alerts_bot`).
3. **Cut-off valve:** a human-operated control that *stops* off-LAN calls (removes/disables the
   credential), and that **the agent cannot operate on itself.**

## Non-goals

- Not production hardening — single-user LAN lab. Don't build per-call human approval UIs.
- Not making Claude the default or an auto-fallback brain. Escalation only.

---

## Verified constraints (from `docs/runbooks/agent-hermes.md`)

- **Provider model:** Hermes runs `custom_providers` in `~/.hermes/config.yaml`; the `model:` key is only
  the *provider default*. The **active** model/provider is set live by the human via `/model [name]
  [--provider n]` — a session-scoped command. Main conversation turns have **no documented cloud
  fallback**; they ride the active selection only.
- **The automatic off-LAN hole:** `auxiliary:` tasks (title-gen, etc.) **default to Nous (cloud)** and
  currently 401 only because no cloud creds exist (runbook "Known noise"). The framework also
  *auto-selects providers per sub-task* (vision auto-detected to local). So automatic provider routing
  machinery exists — it must be pinned, not trusted to "default local."
- **Agent reachability:** Hermes's terminal/sandbox backend is `Local` — the agent runs *inside* CT 104
  with shell tools and runs as `root`. **Anything in CT 104's filesystem (incl. `~/.hermes/.env`) is
  within the agent's potential reach.** A valve in that `.env` is convenient but not agent-proof.
- **Keys live in `~/.hermes/.env`** (the ~23 KB template has every var present/commented), loaded at
  process start → changes need a `hermes-gateway` restart (and `/reload` for the REPL).

### Verified live on CT 104 (2026-06-16) — supersedes runbook assumptions where they differ

- **Main brain:** `model: {default: qwen3-coder:30b, provider: custom, base_url: …244:11434/v1}`.
  **`providers: {}` and `fallback_providers: []` are both EMPTY** → confirmed: **no main-turn cloud
  fallback exists.** Keep `fallback_providers` empty (or local-only) — `hermes fallback` adds providers
  "tried when the primary model fails", i.e. silent auto-escalation. **Never add Claude as a fallback.**
- **The auxiliary auto-path is richer than "defaults to Nous":** `~/.hermes/config.yaml` has an
  `auxiliary:` block with **every sub-task set `provider: auto`** — `vision`, `web_extract`,
  `compression`, `skills_hub`, `approval`, `title_generation`. `auto` = Hermes selects a provider per
  task from configured/pooled providers. **So once the LiteLLM-proxy provider is configured, `auto`
  could route a background task to it → automatic off-LAN spend.** Pinning these to the explicit local
  provider is therefore **mandatory even under Option B** (see gating layer 2).
- **Credential pool:** Hermes has a pooled-credential system (`hermes auth`,
  `credential_pool_strategies: {}`) that feeds the `auto` resolver. **Do not add the Anthropic key to
  the pool** — that would make it `auto`-selectable. (Under Option B there is no Anthropic key on the
  agent at all, so this stays naturally clean.)
- **Intended cloud path is OpenRouter:** the `.env` is OpenRouter-centric ("All LLM calls go through
  OpenRouter — no direct provider keys needed"; every key commented). **Option B uses none of these** —
  leave all `.env` cloud slots commented; Claude rides the LAN proxy as a `custom` provider.
- **Declaring the second provider:** schema is `model:` inline + a `providers: {}` map (the runbook's
  `custom_providers:` *list* is stale drift — note it). Add the proxy provider via **`hermes model`**
  (interactive; writes the correct schema) or `hermes config set`, **not** a hand-edit. There is also a
  `hermes proxy` ("Local OpenAI-compatible proxy to OAuth providers") — *not* our path (that's for
  Hermes-managed OAuth providers; we run our own LiteLLM), but don't confuse the two.

---

## Architecture decision: route Claude through a LAN egress proxy

**Recommended: Option B (proxied).** Two candidate shapes:

### Option A — Direct (lighter, weaker)
Hermes → `api.anthropic.com` directly, with `ANTHROPIC_API_KEY` in CT 104's `~/.hermes/.env`.
- ✅ Minimal infra.
- ❌ Valve lives in CT 104 → **agent-reachable** (the agent could, in principle, re-add its own key).
- ❌ CT 104 gets a live WAN route to Anthropic (departs LAN-only at the network layer).
- ❌ No native per-call/token/spend metrics — would need log-scraping to observe usage.

### Option B — Proxied via LiteLLM on the LAN (recommended)
Hermes → **LiteLLM proxy** (on mother/k3s, `weyland` ns, behind Traefik) → Anthropic.
Hermes is configured with a `custom_provider` pointing at the proxy's OpenAI-compatible `/v1` on the LAN;
the proxy holds the **real** Anthropic key (in a k8s Secret, never committed) and is the sole egress point.

- ✅ **Hermes never gets an off-LAN route** — it only talks to the proxy on the LAN. Preserves the
  LAN-only stance at the network layer; only the proxy (on mother) egresses to Anthropic.
- ✅ **Valve lives outside CT 104** → agent-unreachable. Hard stop = `kubectl scale deploy/litellm
  --replicas=0` (instant; the agent has no kubectl and `/mcp-act` does not expose it). Soft stop =
  LiteLLM admin API disables the virtual key / sets budget 0.
- ✅ **Native observability:** LiteLLM exposes Prometheus `/metrics` (request counts, tokens, spend per
  key/model) → scrape via ServiceMonitor (B5 pattern) → Alertmanager rules.
- ✅ **Native spend caps:** LiteLLM supports per-key budgets + rate limits → the cost ceiling, enforced.
- ✅ **Reusable governance chokepoint** — foreshadows B17+B19's gateway; CT 102/103 could egress through
  it later too.
- ❌ One new service to run (a LiteLLM Deployment + Secret + ServiceMonitor + Ingress).

**The proxy resolves the agent-self-modification problem** that Option A cannot: the credential the agent
might tamper with (in its own `.env`) is only a key to the *LAN proxy*, not to Anthropic. The real key,
the budget, the on/off switch, and the metrics all live on mother, outside the agent's blast radius.

> **Decision needed from operator:** ratify Option B (proxied) vs Option A (direct). Rest of this doc
> assumes B; an A fallback is noted where it differs.

---

## Gating layers (defense in depth)

| # | Layer | Mechanism | Guarantee |
|---|---|---|---|
| 1 | **Explicit provider, never default** | Claude added as a named `custom_provider`; default stays `weyland-ollama`; activated only by `/model --provider`. | Main turns stay local unless a human switches. |
| 2 | **Auxiliary lanes pinned local** | Change **every** `auxiliary.*.provider` from `auto` → `custom` (the local Ollama: `web_extract`, `compression`, `skills_hub`, `approval`, `title_generation`; `vision` needs a local *vision* model — see note). Stops `auto` from ever selecting the proxy/cloud; also fixes the title-gen 401s locally. | No background lane reaches cloud. |
| 3 | **Credential off-box (Option B)** | Real Anthropic key in a k8s Secret on mother; CT 104 holds only a proxy key. | Agent can't acquire the real key. |
| 4 | **Cut-off valve (off-box)** | `kubectl scale deploy/litellm --replicas=0` (hard) / LiteLLM key-disable (soft). | Human stops all off-LAN calls; agent can't undo. |
| 5 | **Spend ceiling** | LiteLLM per-key monthly budget (+ Anthropic Console workspace limit as backstop). | Bounded cost even on mistake. |

Layers 1–2 are the "won't"; layers 3–4 are the "can't"; layer 5 is the financial backstop.

---

## Observability design (req. 2)

**Gate-open signal (primary, zero custom code):** the proxy running *is* the gate being open.
Alert on existing kube-state-metrics:

```
# PrometheusRule (operator CRD), routed to @weyland_alerts_bot via existing Alertmanager config
ALERT  HermesClaudeEgressEnabled
  expr: kube_deployment_status_replicas{namespace="weyland",deployment="litellm"} > 0
  for:  2m
  labels:   { severity: warning }
  annotations:
    summary: "Hermes off-LAN Claude egress (LiteLLM) is RUNNING"
    description: "Hermes can reach Anthropic. Scale litellm to 0 to close the valve."
```

So you get a standing Telegram alert the whole time the valve is open — you can't forget it's on.

**Usage / spend signal (from LiteLLM `/metrics`):**
```
ALERT  HermesClaudeSpendHigh
  expr: increase(litellm_spend_metric{model=~"claude.*"}[24h]) > <USD_THRESHOLD>
  ...
ALERT  HermesClaudeCallsObserved   # optional: any off-LAN call at all
  expr: increase(litellm_proxy_total_requests{model=~"claude.*"}[5m]) > 0
```

**Option A fallback (no proxy):** push a `hermes_claude_enabled{0|1}` gauge from the valve script to a
**Pushgateway** (one small in-cluster Deployment Prometheus already scrapes), then alert on `== 1`.
Per-call/spend metrics are not available without log-scraping.

---

## Cut-off valve design (req. 3)

**Hard stop (instant, agent-proof, Option B):**
```
kubectl scale deploy/litellm -n weyland --replicas=0   # drops in-flight; Hermes' next Claude turn fails closed
```
Wrap as `hermes-claude-valve {close|open|status}` on **mother/rogueone** (NOT CT 104):
- `close` → scale 0 (+ optionally `kubectl delete secret litellm-anthropic-key` for belt-and-suspenders).
- `open`  → scale 1 (recreate Secret if deleted).
- `status`→ replica count + last 24h `litellm_spend_metric`.

**Soft stop (Option B):** LiteLLM admin API — disable the virtual key or set its budget to 0. Keeps the
proxy up (other potential consumers unaffected) but Claude routes 4xx.

**Why off-box matters:** because Hermes runs as root inside CT 104 with shell tools, a valve *inside* 104
is theoretically self-reversible by the agent. Hosting the valve on mother (k8s control plane, which the
agent has no client for and `/mcp-act` does not expose) makes it a true human-only control.

> **Option A valve (if chosen):** a root-owned `claude-valve.sh {close|open}` on CT 104 that comments the
> key out of `.env` and `systemctl restart hermes-gateway`. Accept the agent-reachability caveat, or
> additionally run the gateway as a non-root user that cannot write a root-owned `.env` (larger change).

---

## Open verification items (run on CT 104 before building)

These close the two residual uncertainties from the runbook read:

```bash
# 1) Does an auxiliary task config block exist, and where does it point today?
pct exec 104 -- bash -lc 'grep -n -A3 -iE "auxiliary|aux_provider|title" ~/.hermes/config.yaml || echo "no auxiliary block (uses Nous default)"'

# 2) Show the full provider + any fallback config (confirm no undocumented main-turn cloud fallback)
pct exec 104 -- bash -lc 'sed -n "1,200p" ~/.hermes/config.yaml'

# 3) Confirm how Hermes expects a *second* provider declared (custom vs native anthropic)
pct exec 104 -- bash -lc 'hermes --help 2>&1 | head -50; echo ---; hermes config --help 2>&1 | head -40'
#    NB: provider-switching (`/model --provider`) is an in-REPL slash command — confirm its flags inside `hermes`, not the shell

# 4) Confirm the .env slot name for the Anthropic key (Option A) / proxy key (Option B)
pct exec 104 -- bash -lc 'grep -niE "anthropic|claude|openrouter|api_key" ~/.hermes/.env | head'
```

---

## Rollout (Option B)

1. **Verify** (above). Confirm auxiliary lane target + provider-declaration shape.
2. ✅ **DONE 2026-06-17** — text lanes (`title_generation`, `web_extract`, `compression`, `skills_hub`,
   `approval`) pinned to local Ollama; 401/Nous noise gone, main turns stay local. `vision` deferred
   (needs a local vision model). Original step:
   **Pin auxiliary lanes → local** (gating layer 2): set each `auxiliary.*.provider: custom` with the
   local Ollama `base_url`/`api_key`/`model` (text lanes use `qwen3-coder:30b`). `vision` needs a local
   vision-capable model (e.g. `mistral-small3.2:24b` if pulled) — pin it there, or accept it's the one
   lane that may fail-closed rather than route out (rare in this lab). Confirm the title-gen 401 noise
   stops. *Do this first — it's the safety fix, valuable even if B26 stops here, and it must land before
   the proxy provider is added (so `auto` can never pick the proxy).*
3. **Deploy LiteLLM** to `weyland` ns: Deployment + Service + ServiceMonitor + Traefik Ingress
   (`litellm.weyland.lab`) + Secret `litellm-anthropic-key` (uncommitted). Configure the Claude route
   (`claude-sonnet-4-6` to start; `claude-opus-4-8` reserved) + a per-key monthly budget.
4. **Set Anthropic Console** workspace spend limit on a dedicated key (layer 5 backstop).
5. **Register the proxy in Hermes** as a `custom_provider` (base_url → the LAN proxy `/v1`); leave default
   = `weyland-ollama`. Test escalation with `/model --provider`.
6. **Add PrometheusRules** (gate-open + spend) and confirm they route to `@weyland_alerts_bot`.
7. **Install the valve** (`hermes-claude-valve`) on mother/rogueone; test `close` drops a live Claude turn.
8. **Update registries:** add `litellm.weyland.lab` to `docs/hosts.md`, the proxy endpoint to
   `docs/api.md`, and the egress edge to `docs/arch.md` (per the keep-registries-updated rule).

## Acceptance

- Default conversation + all background lanes provably local (auxiliary 401s gone; `/usage` shows local).
- `/model --provider <claude>` escalates a turn; switching back returns to local.
- Telegram alert fires within ~2 min of the valve opening and resolves when closed.
- `hermes-claude-valve close` stops Claude turns and **cannot be reversed from inside CT 104**.
- Spend alert fires past the configured threshold; LiteLLM budget caps hard.
