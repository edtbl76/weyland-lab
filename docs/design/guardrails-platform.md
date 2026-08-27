# Guardrails platform — defense-in-depth (design) — **B115**

**Goal:** a four-layer guardrails stack, each layer a distinct *path* doing one job — matching the industry-standard
pattern (production stacks run 2–3 of these; they're **complementary, not competing**). All four are OSS/self-host →
**$0**. Decided 2026-08-03 (reverses the earlier "skip NeMo" lean after evaluating the landscape: NeMo is the *standard*
for a layer we hadn't built — dialog control — so we adopt it as one of four, rather than skip).

## The four paths

| # | Path | Tool | Job | Where it sits |
|---|------|------|-----|---------------|
| 1 | **Scan** | **weyland-guard** (≈ LLM Guard, Protect AI) | I/O sanitization — injection / toxicity / grounding / PII on inputs + outputs | the fast **first layer**, at the agent edge + the MCP gateway. Already LIVE (B14 + B34 PII + B35 grounding) |
| 2 | **Classify** | **Llama Guard** (Meta) | model-based **content-safety classification** (safe/unsafe + violated categories) | a self-hosted classifier the Scan layer can call for a second opinion |
| 3 | **Dialog** | **NeMo Guardrails** (NVIDIA) | **topical / conversational-flow** control (Colang rails) | wraps a **conversational** surface (Open WebUI / a chat lane), NOT the tool-calling operator |
| 4 | **Structure** | **Guardrails AI** | **output-schema validation** — validate + re-ask on failure | on **structured-output** producers (extraction, the eval-judge JSON, structured agent deliverables) |

## How they compose
The industry pattern: **Scan** (fast, every request) → **Classify** (model-based safety, when the scan wants a stronger
call) → **Dialog** (only on conversational surfaces) → **Structure** (only on structured-output tasks). Not every layer
on every request — each runs on the surface where it earns its keep. Scan stays the always-on baseline; the others are
per-surface. The lab's existing **pre-action authorization** (the operator's confirm-rails + enforcing `policy.gate`)
and **offline eval** (B84/MLflow) sit alongside as the act-safety and quality lanes.

## Placement in the lab
- **Scan** → weyland-guard (edge, all agents) — already there; optionally graft LLM Guard's scanner set.
- **Classify** → **two tiers**: (a) **Llama-Guard-3-1B always-on on CPU (mother)** — the *default*, always-available classifier weyland-guard calls on every classify (Kokoro-style small service; no GPU contention/freeze, $0, no cold-start on the guard path); (b) **Llama-Guard-3-8B on-demand on the rogueone GPU** (vLLM, the B111 pattern) — the *stronger* escalation for calls that need a heavier verdict (e.g. the 1B is uncertain / high-risk context).
- **Dialog** → NeMo wrapping the **Open WebUI / chat** lane (topical control for the browser assistant, where dialogue policy matters).
- **Structure** → Guardrails AI on structured-output agents/tasks.

## Cost
**$0** — all OSS/self-host. Llama Guard runs on the rogueone GPU already serving vLLM/SGLang (on-demand). No SaaS.

## Build order
1. **Llama Guard — 1B always-on CPU (mother)** first (the default classifier; `llama.cpp` server, ungated GGUF, temp 0), then the **8B on-demand GPU (rogueone)** escalation (`llama.cpp` server-cuda, same stack). ⬅ FIRST
2. **Guardrails AI** — on a real structured-output task.
3. **NeMo** (dialog) — on the Open WebUI / chat surface (the trial config already exists: `scripts/nemo-guardrails-trial/`).
4. **Scan** — already live; augment if wanted.

Relates: [[weyland-guard-b70]], B14 (guardrails), [[b34-pii-guard]], [[b35-grounding-calibration]], B32 (NeMo → adopt),
[[gpu-inference-vllm-sglang-b111]] (the rogueone serving pattern Llama Guard reuses).
