# Bifrost Provider Load-out (B111) — tracking

Live status of every provider we're loading into Bifrost (`bifrost.weyland.lab`), the agent-edge LLM gateway.
Keys live in `/home/edwardmangini/IdeaProjects/weyland/scripts/.env` (gitignored). This file is the running list — update
it as each provider is proven/parked. At codification (end of load-out) this folds into the runbook + a SealedSecret +
init-seeded Bifrost config.

**Two bars — connectivity ≠ agent-readiness.** A tool-free `200` proves the key/route/provider work. But Bifrost is the
**agent edge**, so the real bar is **tool-calling works through the provider** with the fleet attached. That's harder:
the model must (a) support tool-calling and (b) fit the ~21k-token tool payload within its context/limits/budget.
Current ✅ marks = **connectivity proven**; each still needs a **tool-calling pass** before it's agent-ready. Groq free
is chat-only (TPM cap) — so it's connectivity-✅ but **not** agent-ready. Budgeted/paid providers carry tools fine.

**PLAN (2026-07-30):** validate **connectivity (tool-free) across ALL providers first**, THEN run the **tool-calling
validation later on paid/budgeted providers** ("real moolah") where the ~21k-token tool payload is affordable — not the
free-capped ones (Groq/Ollama/HF-credits stay chat-validated). Tool-calling pass = separate phase after the key load-out.

**TOOL-CALLING PASS ✅ DONE 2026-08-03 — 7/7 paid providers PASS** transparent tool-calling through Bifrost
(anthropic · openai · opencode-zen · xai · deepseek · cerebras · openrouter — each returned a proper `get_weather`
tool_call with the fleet auto-inject suppressed via empty `x-bf-mcp-include-tools`). Confirms the passthrough MLflow's
gateway broke. **Re-runnable conformance test kept: `scripts/validate_bifrost_tool_calling.py`.** Groq/Ollama/HF remain
chat-validated only (free-capped / self-hosted TBD). **This closes B111.**

**Status legend**
- ✅ **LIVE** — smoke returned `200` in-path; feeding Observability.
- 💳 **PAYWALLED** — key valid but provider gates inference (`402`/credits). NOT dead — **enable behind a hard Bifrost
  budget cap** so it can't run away spend. Tracked deliberately (this is why we care about Budgets & Limits).
- ⏸️ **PARKED** — blocked by a Bifrost-side bug, not our config. Revisit.
- 🔜 **PENDING** — key present, not yet added/tested.
- ⛔ **SKIP** — deliberately excluded (no free path + no reason, or user policy).

## Smoke command (in-path, in-cluster)

```
kubectl -n weyland exec deploy/weyland-guard -- python -c 'import httpx; r=httpx.post("http://bifrost.weyland.svc.cluster.local:8080/v1/chat/completions",json={"model":"<provider>/<model>","messages":[{"role":"user","content":"say hi in 3 words"}]},timeout=60); print(r.status_code); print(r.text[:600])'
```
List a provider's real (key-entitled) models: `GET /api/models?provider=<name>&unfiltered=true` — Bifrost's static
datasheet can list models the key can't access (that's a `404` on call, not a config error).

## Routing design (2026-07-31) — use case first, then cost/availability

> **⚠️ TOOL PIVOTED (2026-07-31): routing runs on LiteLLM, NOT Bifrost.** The 9 Bifrost routing rules below were
> BUILT then WIPED — Bifrost OSS routing/failover is Enterprise-gated (`chain_rule` ≠ fallback; adaptive-LB paywalled;
> VK `provider_configs` can't resolve self-hosted keys). The **design** (aliases + cost-ordered chains) stands; only the
> tool changed. Now LIVE in LiteLLM `k8s/litellm/configmap.yaml` (`model_list` + `router_settings.fallbacks`), verified
> (routing + fallback firing). Map `docs/llm-routing-map.html`, runbook `docs/runbooks/model-gateway.md § 1b`.

**Principle:** route by **use case** (primary axis), then within it by **real cost** (free/self-hosted → free-hosted →
cheapest *paid source of that model* → premium) with availability fallback. Clients request a **use-case alias**
(`wl-coding`, `wl-rag`, …); CEL rules resolve it.

### ✅ BUILT 2026-07-31 — 9 use-case alias rules live (`scripts/register_bifrost_routing.py`, idempotent)

**Mechanism (v1.6.7, reverse-engineered — docs page 404'd):** `POST /api/governance/routing-rules`
`{name, cel_expression, targets:[{provider,model,weight}], scope:"global", priority, chain_rule}`. CEL vars: `model`,
`provider`, `request_type`, `budget_used` (%), `tokens_used` (%), `request` (%), `headers[...]`, `team_name`. **Targets are
WEIGHTED (probabilistic split), NOT ordered fallback** — so each rule sets the PRIMARY. Routing runs *before* governance
provider-selection and can override it. Rules persist in Bifrost's PVC DB (not a k8s manifest → Argo won't revert); the
script is the source of truth.

**VERIFIED FINDING — `chain_rule` is NOT on-failure fallback (2026-07-31).** Tested empirically: a rule targeting a
genuinely-down provider (vLLM off → `502 provider_connection_failed`, `connection refused` — the documented fallback
trigger) with `chain_rule:true` + a second same-CEL Groq rung **did not cascade** — the request failed on the primary.
(Three earlier tests short-circuited on pre-flight 400/404s that never hit a socket; the vLLM test is the clean one.)
**So availability fallback CANNOT live in routing rules.** Bifrost's real failover is **request-level** (`fallbacks:[...]`
array in the request body — client must send it) or **VK-level** (`provider_configs` on a virtual key — server-side,
applies to all requests on that key but coarse: one chain per key, not per-alias). Cost-degrade (`budget_used > N → free`)
IS expressible as a normal routing rule (CEL var confirmed) but wasn't trigger-tested (needs 90% spend).

| Alias | → Primary | Why |
|---|---|---|
| `wl-default` | groq/openai/gpt-oss-120b | free hosted general |
| `wl-speed` | groq/openai/gpt-oss-120b | free hosted, fast |
| `wl-coding` | opencode-zen/kimi-k3 | coding specialist + tool-capable |
| `wl-agentic` | anthropic/claude-haiku-4-5 | reliable cheap tool-calling |
| `wl-rag` | ollama/gpt-oss:20b | free local (private) |
| `wl-reason` | ollama/qwen3:30b-a3b | free local reasoning |
| `wl-judge` | ollama/qwen2.5:7b | free local judge (the current one) |
| `wl-search` | perplexity/sonar | ONLY web-search provider |
| `wl-big-oss` | openrouter/minimax/minimax-m3 | big frontier OSS via aggregator |

**Verified 2026-07-31:** all 9 route correctly end-to-end (coding→kimi-k3, agentic→haiku, search→sonar, big-oss→minimax-m3,
rag→ollama). **Availability caveat:** ollama-local primaries (rag/reason/judge) fail when rogueone sleeps — but this MATCHES
the existing RAG architecture (generation was always rogueone-local), so it's not a new dependency; `wl-default`/`wl-speed`
are the always-on (groq) general aliases.
**Remaining Bifrost routing work (needs a decision — see finding above):** (1) **availability fallback** — not doable in
routing rules (chain_rule proven inert); choose VK `provider_configs` (server-side, coarse) vs robust groq primaries for
rag/reason/judge vs accept the caveat; (2) `budget_used > 90 → free` cost-degrade overflow rules (buildable now, trigger-
test deferred); (3) **media lane ✅ DONE** — image (**Runware** ✅ `runware:100@1`), tts (**Kokoro** ✅ self-hosted
PRIMARY `kokoro/kokoro`; **ElevenLabs deferred** — free tier blocks library voices via API), video (**Runway** ✅ funded,
async submit→poll). LiteLLM route: `wl-tts` PRIMARY `openai/kokoro/kokoro` (via Bifrost) → `elevenlabs-tts` fallback
(`router_settings.fallbacks`). **GOTCHA:** the `realm-llm` Bifrost VK must allow the `kokoro`/`elevenlabs` providers or
LiteLLM egress returns 500 "Provider 'kokoro' is not allowed for this virtual key" — this VK allow-list is out-of-band
(config.db), so on a Bifrost wipe it must be re-added.

**Use cases:** coding · agentic · rag · search · reason · judge · default · **speed** · **big-oss** · **video** (+ media: tts, image).

**Provider → role (post-walkthrough):**
- **Primaries:** Anthropic (coding-escalation/agentic-tools) · OpenCode-Zen (coding, kimi-k3) · Cohere (rag) · Perplexity
  (search — unique) · Gemini (free, long-context/default) · Groq (default/free-speed, tool-free) · Ollama (free-local
  workhorse) · OpenRouter (aggregator/free/big-oss) · Runware (image) · Kokoro (tts — self-hosted primary; ElevenLabs
  deferred alternate) · Runway (video) · xAI
  (reason + real-time/X-data) · vLLM (throughput, self-hosted) · SGLang (prefix-cache, self-hosted).
- **Misc / conditional:** Cerebras (speed — paid tier w/ TPM headroom for tool-heavy OSS, above free Groq) · DeepSeek-direct
  (reason — cheapest-DeepSeek once Fireworks free credits deplete; one-time $1 credit = sunk) · Fireworks (paid OSS+tools,
  no free tier after credits) · OpenAI (premium/unfunded — o-series/gpt-image) · HuggingFace (aggregator, burns credits —
  overlaps OpenRouter) · Mistral (Codestral FIM code-completion) · Replicate (long-tail ML: upscale/SAM/restore/music/3D +
  video fallback).
- **🗑️ DELETED:** Parasail (Qwen redundant — free via Ollama/Groq/OpenRouter) · Wafer (big-oss covered by OpenRouter at
  par; price-checked). Both: API-deleted + stripped from the 3 scripts + budgets dropped.

**Cost gotchas that shaped this:** Fireworks free credit is ONE-TIME ($1, sunk — judge on base PAYG) → DeepSeek-direct is
the cheaper DeepSeek source. Cerebras/Groq differ on **capacity not capability** (same tool-calling; Groq-free 8000 TPM
chokes on the ~21k fleet-tool payload, Cerebras-paid fits it). "Cheapest source of the model," not cheapest provider.

## KEY FINDING (2026-07-30) — Bifrost auto-injects the 91 fleet MCP tools into EVERY chat completion

Proven on Groq (both `is_bifrost_error:false`, i.e. Groq's own responses):
- `groq/openai/gpt-oss-120b` → **`413`** "Request too large … Requested **21789** tokens" (a 3-word prompt; the 21k is
  the fleet tool schemas — ~91 × ~240 tok — blowing past Groq free-tier **8000 TPM**).
- `groq/groq/compound` → **`400`** "`tool calling` is not supported with this model" (compound rejects the tools Bifrost
  attached, though our request asked for none).

**Scope: this is a GROQ-SPECIFIC corner, NOT a platform problem.** Tool injection is the *feature* (Bifrost = agent edge;
tools should flow) — it's just tokens everywhere else, governed by budgets. Groq is the exception ONLY because its free
tier caps at **8000 TPM** and Dev-tier upgrade (pay-per-token) is blocked, so the ~21k tool payload can't fit and can't be
paid around. Do NOT globally disable tool injection — that throws away the agentic capability to solve one provider's cap.

**CONFIRMED FIX (2026-07-30):** sending an **empty `x-bf-mcp-include-tools` header** suppresses auto-injection (deny-by-
default: empty include-list = no tools) → `groq/openai/gpt-oss-120b` returned **`200`** on the free tier. Mechanism:
Bifrost auto-generates `x-bf-mcp-include-tools` from VK config unless the caller sends the header OR
`mcp.toolManagerConfig.disableAutoToolInject: true` is set.

**Handling — per provider, NOT global:**
- **Groq (free, can't pay):** use a **tool-free path** — either send empty `x-bf-mcp-include-tools`, or give Groq's VK an
  empty MCP config. Groq is limited to tool-free / small chat by its own 8000 TPM cap. This is the ONLY provider we
  de-tool, and only because pay-per-token is blocked.
- **Everyone else:** keep tools injected (it's the point). Control cost with **Budgets & Limits** (per-provider + per-VK
  hard caps), not by stripping tools. A paid provider with a budget cap carrying 21k tool-tokens is fine — that's spend
  governance, which is what B111's VK budgets are for.
- **Do NOT** set `disableAutoToolInject` globally — it would kill the agent-edge feature to patch one provider's free cap.

Note: our smoke command below sends the empty header purely so the *smoke* is cheap/representative of tool-free chat — it
is not the production posture for paid providers.

## Load-out

| Provider | Bifrost type | Status | Proven model | Notes / budget plan |
|---|---|---|---|---|
| xAI | native `xai` | ✅ LIVE | `xai/grok-3` | Was `403` (no credits) → added $5. **Set a monthly budget cap** — paid, no free tier. |
| Groq | native `groq` | ✅ LIVE (tool-free) | `openai/gpt-oss-120b` | Signup fixed. Free tier **8000 TPM** + pay-per-token blocked → **tool-free only** (empty `x-bf-mcp-include-tools`; tools = ~21k tok = `413`). Entitled chat models: `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `qwen/qwen3.6-27b`, `llama-3.1-8b-instant`. `groq/compound` rejects tool-calling. |
| Hugging Face | native `huggingface` | ✅ LIVE | `cerebras/openai/gpt-oss-120b` | **The multiplier** — one key fronts HF **Inference Providers** router (`<provider>/<org>/<model>`): cerebras/cohere/deepinfra/etc, TONS of models. Routes consume HF **free credits** (limited) → watch budget. Model list via `/api/models?provider=huggingface`. |
| Cerebras | native `cerebras` | 💳 PAYWALLED | — (`402` on `gpt-oss-120b`) | Key valid, models entitled, inference is `402`. Add later **only behind a budget cap**; free listing, paid execution. |
| Parasail | native `parasail` | 🗑️ DELETED 2026-07-31 | — | **Shitcanned** — Qwen hosting is redundant (free via Ollama/Groq/OpenRouter, hosted elsewhere); no unique edge + paywalled. Removed: provider (API), budget, and from all 3 scripts (seal/providers/governance). Orphan sealed key drops on next re-seal. |
| Replicate | native `replicate` | 💳 PAYWALLED | — (`402` on `anthropic/claude-4.5-haiku`) | Key valid + catalog visible (hosts Claude chat + flux image/video), but `402` "insufficient credit." Multi-modal. Revisit **behind a budget cap** once funded. |
| Runway | native `runway` | ✅ LIVE (video) | `gen4_turbo` | **Video-only, not chat. FUNDED 2026-08-02 (2000 credits) → video works.** Async image-to-video: `POST /v1/videos` → `status:queued` + task id → poll `GET /v1/videos/{id}` until `status:completed` (returns an `.mp4` URL), ~30-90s. Shape = `model`+`prompt`+`input_reference` image+`seconds:"5"`(not 2)+`size` "1280x720". Bifrost tries **Replicate** first (paywalled) → falls back to Runway automatically. `gen4_turbo`/`gen3a_turbo` = image-to-video; `gen4.5` etc. Paid → budget cap. |
| Runware | native `runware` | ✅ LIVE (image gen) | `runware:100@1` (FLUX.1 schnell) | **Image-only, not chat.** `POST /v1/images/generations` (OpenAI-style `model`+`prompt`+`size`+`n`) → `200` + real image URL (`im.runware.ai/…`), 2.08s. Cheap/free-credit → cleared where Runway paywalled. Bifrost datasheet empty for runware → model = **AIR identifier** `source:id@version` (`runware:100@1`); browse via Runware's Model Search. |
| Together AI | custom OpenAI-compat | ⏸️ PARKED | — | base_url `https://api.together.xyz/v1` correct, key present; Bifrost returns the Together **website** (Next.js 404) — custom-provider routing bug, not our config. Direct `api.together.xyz` works. |
| AWS Bedrock / Bedrock Mantle | native `bedrock` / `bedrock_mantle` | ⛔ SKIP | — | No free tier; only $200 new-account credit. `bedrock_mantle` = Bearer-key path (vs SigV4). Revisit only with unspent AWS credits + budget cap. |
| Azure OpenAI | native `azure` | ⛔ SKIP | — | User policy (no MS). |
| Vertex AI | native `vertex` | ⛔ SKIP | — | **Deprecated — killed 2026-07-31.** Not pursuing. |
| Nebius (Token Factory) | native `nebius` | ⛔ SKIP | — | **Killed 2026-07-31 — couldn't create an account.** |
| Sarvam AI | native `sarvam` | ⛔ SKIP | — | **Skipped 2026-07-31 — Indic-language specialized, not the lab's use.** |
| OpenCode Go | — | ⛔ SKIP | — | Subscription-based (not PAYG); chose OpenCode **Zen** (pay-as-you-go) instead. |
| vLLM | native `vllm` | ✅ LIVE (P1 + use case b DONE) | `Qwen2.5-7B-Instruct-AWQ` | On-demand Docker on rogueone GPU via `nodes/rogueone/services/gpu-inference/`. **Must run on NATIVE engine** (`DOCKER_HOST=unix:///var/run/docker.sock` — Desktop=default context, no GPU). Base URL `http://192.168.1.230:8001` (no `/v1`). VRAM: `--gpu-memory-utilization 0.55` (0.25 gave NEGATIVE KV cache). **Continuous-batching bench 2026-07-31: 88.9→1329.5 tok/s (~15×) at conc 1→16, flat latency.** Docs: runbook + demo (extreme detail) + memory [[gpu-inference-vllm-sglang-b111]]. |
| SGLang | native `sgl` | ✅ LIVE — role = **PREFIX CACHING** | `unsloth/Llama-3.2-1B-Instruct` | On-demand, native engine, `:8002`, Bifrost `sgl`, `scripts/sglang-bench.sh`. Model = ungated Llama-3.2-1B mirror (Meta 403-gated; `unsloth/…` skips it). **SGLang's distinct value = RadixAttention prefix caching** for agent/RAG (fat repeated system prompts): measured **~6.2× faster TTFT on cache hits** (26ms hit vs 164ms miss, 2.5K-token shared prefix; `prefix_cache_bench.py`). Gotchas: `--mem-fraction-static` goes HIGHER not lower (opposite of vLLM); PD/disaggregation **REJECTED** (needs ≥2 GPUs; CPU-decode dead on non-AMX i9). |
| Ollama | native `ollama` | ✅ LIVE (chat; tool-calling TBD) | `qwen2.5:7b` | **Free, in-house** — rogueone `http://192.168.1.230:11434`, **no API key** (dummy if field required). GOTCHA: Bifrost blocks private/LAN IPs by default (SSRF guard) → must enable **"allow private network"**. No `/v1` on base URL; disable health-ping if it false-flags. Tool-capable models: `qwen2.5:7b` (VRAM-safe), `gpt-oss:20b` (heavy), `qwen3:14b`/`qwen3:30b-a3b`. **Tool-calling test pending** — needs scoped tool subset + raised `num_ctx` (default too small for 21k tools) + VRAM care on the 16GB card ([[rogueone-gpu-freeze-vram]]). |
| OpenCode Zen | native `opencode-zen` | ✅ LIVE | `kimi-k3` | Native in this Bifrost build (not in upstream docs). **PAYG**, funded $20 → budget-cap candidate. Tons of models (coding-focused: kimi-k3, etc.) → prime target for the paid tool-calling pass. (OpenCode *Go* = subscription, skipped in favor of Zen PAYG.) |
| Kokoro | custom (openai base) | ✅ LIVE (tts, non-chat) | `kokoro/kokoro` (voice `af_bella`) | **TTS PRIMARY — self-hosted, $0, no quota.** Kokoro-FastAPI (Apache-2.0, ~82M model, CPU-only) at `kokoro.weyland.svc:8880`, OpenAI-compatible `/v1/audio/speech`; fronted by Bifrost as a **custom provider** `kokoro` (`base_provider_type: openai`, `allow_private_network: true`). Voices `af_bella`/`am_adam`/`bf_emma`. Web player UI at `kokoro.weyland.lab` (forward-auth), Argo-managed (`k8s/kokoro/`). Durable via `scripts/register_bifrost_kokoro.py`. |
| ElevenLabs | native `elevenlabs` | ✅ LIVE (speech, non-chat) — **DEFERRED alternate** | `eleven_multilingual_v2` | **TTS/STT, not chat** — validated via `/v1/audio/speech` → `200` `audio/mpeg` 27KB. **NOT primary** (Kokoro is): free tier **blocks library voices + voice cloning via the API** (`402` "Free users cannot use library voices via the API") → credits unspendable except on a paid plan. **Request shape** (this build): `model:"elevenlabs/eleven_multilingual_v2"` + **`voice` field REQUIRED** (voice IDs from ElevenLabs `/v1/voices`, `xi-api-key` header). Kept as the `wl-tts` fallback rung. Paid → budget cap. Use **ElevenCreative** platform (not ElevenAgents). |
| Anthropic | native `anthropic` | ✅ LIVE | `claude-haiku-4-5` | Keys confirmed in Bifrost native. Paid → budget cap. |
| OpenAI | native `openai` | 💳 PAYWALLED | — | Key valid; `429 insufficient_quota` — no credit/billing. Also hosts image models (dall-e/gpt-image). Revisit behind a cap once funded. |
| Gemini | native `gemini` | 💳 QUOTA | — | Key valid; `429 RESOURCE_EXHAUSTED` — quota hit. **May be free-tier rate limit (retryable)** vs hard billing — retry before concluding paywalled. |
| Perplexity | native `perplexity` | ✅ LIVE | `sonar` | Paid, **no free tier** — response reports `cost` (~**$0.005/req** incl. search fee) → budget-cap candidate. |
| OpenRouter | native `openrouter` | ✅ LIVE | `amazon/nova-lite-v1` | Free/cheap models available (`:free` suffix). |
| Cohere | native `cohere` | ✅ LIVE | `command-a-03-2025` | |
| Mistral | native `mistral` | ✅ LIVE | `mistral-small-latest` | |
| Fireworks | native `fireworks` | ✅ LIVE | `accounts/fireworks/models/gpt-oss-20b` | Model = `accounts/fireworks/models/<name>`. **Bifrost datasheet STALE** (shows deprecated code-llama); use current serverless: `gpt-oss-{20b,120b}`, `llama-v3p3-70b-instruct`, `qwen2p5-*`, `kimi-k2-*`, `deepseek-v3*`. Paid (free credits) → budget cap. |
| DeepSeek | native `deepseek` | 💳 PAYWALLED | — | Key valid; `402 Insufficient Balance`. Revisit behind a cap once funded. |
| Wafer | native `wafer` | 💳 PAYWALLED | — | Key valid; `402 insufficient_credits` ($0 balance). Serves big models (GLM-5.x, Kimi-K3, MiniMax-M3, Qwen3.5-397B). Revisit behind a cap once funded. |

## Bifrost enterprise tier — NOT purchasing (2026-07-31)

Bifrost's paid/enterprise-gated **features** (not models) are a non-issue for a single-node $0 lab — each is irrelevant
or already backfilled free by the existing stack: guardrails → `weyland-guard` + MLflow-gateway judges · observability/
analytics → MLflow Traces + LGTM · SSO/RBAC → Keycloak forward-auth · governance/budgets → the OSS API (done above) ·
clustering/HA → moot on one node. Decision: stay on Bifrost OSS.

## Key-sealing — DONE 2026-07-31 (SealedSecret + env-ref keys, zero plaintext in PVC)

All 21 provider keys sealed: `scripts/seal_bifrost_keys.sh` builds a Secret from `scripts/.env` → `kubeseal` → writes
`k8s/sealed-secrets/sealed/weyland__bifrost-provider-keys.yaml` (encrypted, safe to commit). `bifrost.yaml` mounts it via
`envFrom` (optional). `scripts/register_bifrost_providers.py` points each provider's key at **`env.VAR`** (add-pass, then
`--purge` drops plaintext). Verified: every provider = 1 key, **type=`env`**, 0 plaintext; smokes pass; API shows keys
redacted. Restore-from-scratch: apply SealedSecret → restart Bifrost → run the script.
**GOTCHAS:** (1) adding `envFrom` did NOT auto-roll the pod — needed `kubectl rollout restart deploy/bifrost` to mount
the env. (2) Env-backed keys read back as `type=env` with a REDACTED resolved value (not the literal `env.VAR`) — the
idempotency check keys on `type==env` + name `-env`. (3) `bifrost.yaml` envFrom MUST be pushed to git or Argo selfHeal
reverts it → env empties → outage.

## Budgets — DONE 2026-07-31 (per-provider, scripted)

**18 per-provider monthly caps SET** via `scripts/register_bifrost_governance.py` (idempotent): Anthropic **$20**, all
other paid providers **$10/mo** each (openai/gemini/deepseek/cohere/mistral/openrouter/perplexity/fireworks/xai/opencode-zen/
cerebras/parasail/replicate/runway/runware/wafer/elevenlabs). Free/self-hosted (ollama/vllm/sgl/huggingface/groq) uncapped.

**v1.6.7 mechanism (GOTCHA — the docs describe a NEWER unreleased schema):** budgets are NOT on VKs. They're on a
**model-config** = `(provider, model_name, scope)`, created via `POST /api/governance/model-configs` with nested
`budgets:[{max_limit, reset_duration:"1M"}]`. `model_name:"*"`=All Models, `scope:"global"`=all traffic for that provider.
`POST /api/governance/budgets` is **405** (read-only view). In v1.6.7 VKs carry identity + tool-scoping, NOT budgets (the
VK `budget` field the docs show doesn't exist yet — v1.6.7 IS the latest release, no upgrade available). Verify:
`GET /api/governance/model-configs`. The 3 consumer VKs (coding-agents/operator/chat-eval) exist for edge auth; values sealed.

## Budget/Limit posture (the point of tracking paywalls)

Every 💳 and paid ✅ provider gets a **hard cap** in Bifrost **Budgets & Limits** before it's trusted in a VK:
- per-provider monthly ceiling (reject over budget), and/or
- per-virtual-key budget so a coding-agent key can't run up a paid provider.
This is what lets us safely *keep* paywalled providers configured instead of skipping them — the cap is the safety net.
