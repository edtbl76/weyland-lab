# B14 — Guardrail Layer: Design Spec (2026-06-15)

## Context & goal

Enable runtime LLM I/O safety on weyland as a **learning + agent-prep** track (single-user LAN lab — *not*
production hardening). Three drivers, in priority: **(A)** hands-on with a *broad, swappable* guardrails stack;
**(B)** prompt-injection awareness (agents now read untrusted RAG'd content + Tavily web); **(C)** grounding
enforcement on `/context/ask`. **(D)** read+act (turning on the write/act MCP tools) lands *after* this layer,
gated behind it.

**Design stance (decided in brainstorming):**
- **Flexible, pluggable stack** — not one locked-in tool. Adding a guardrail = registering a validator + a
  config line.
- **Layered (target), built incrementally.** Layer 1 = tool-server (system/data boundary) — *this spec*.
  Layer 2 = Hermes agent (reasoning-loop boundary) — deferred to D, where the agent acts autonomously on
  untrusted content. Layers must guard *different boundaries* (no running the same check twice).
- **Shadow-first.** Validators observe and record before they enforce.
- **Verdict stream = a data product.** Every validator firing is structured telemetry → Grafana now → a
  **B1 data-mesh data product** later.

## Architecture

A **guardrail pipeline** as middleware inside the **tool-server** (the seam — protects every MCP consumer:
Hermes, Claude Code, OpenClaw, uniformly). Request flow:

```
request → [input validators] → real route (/context/ask, /context/search) → [output validators] → response
                         ↘ every verdict → guardrail_verdicts table + Prometheus metric ↙
```

- **Layer 1 (this spec):** tool-server pipeline. Sees tool calls + retrieved content + answers.
- **Layer 2 (deferred → D):** Hermes agent-side hooks. Sees the agent's full reasoning context (e.g. a
  malicious instruction in a Tavily result) that the tool-server never sees.

## Validator contract (the pluggability)

Each validator is a small, independently-testable unit:

```
Validator.check(payload, hook) -> Verdict {
    decision: "pass" | "flag" | "block",
    score: float | None,
    reason: str,
    validator: str,
    latency_ms: int,
}
```

**Config (not code)** maps hook points → ordered validator chains, each with a **mode**:
`off` | `shadow` | `flag` | `block`. `shadow` computes + records the verdict but never alters the response;
`flag` annotates the response; `block` rejects. Mode is **per-validator**, so you promote each one
independently as you gain confidence.

## Hook points

- **`input`** — the query and the retrieved chunks (untrusted content), on `/context/ask` and `/context/search`.
- **`output`** — the grounded answer, on `/context/ask`.
- **`act`** — reserved for **D** (validating `/pipeline/trigger`, `/evals/run`, `/evals/score`). Not in this pass.

## Verdict store + observability — the data product

Table **`guardrail_verdicts`** (reuses Postgres, the eval-store pattern):
`id, request_id, hook, validator, mode, decision, score, reason, latency_ms, created_at`.
Every run is logged regardless of mode. Surfaced as **Prometheus metrics → Grafana** (reuses B5). Structured
from day one so it slots into **B1 (data mesh)** as the "guardrail telemetry" data product — turning the
guardrail layer into a *measurement* surface before an enforcement one ("measure, don't assume").

## Initial broad stack (all ship in `shadow`)

| Validator | Tool | Venue | Hook(s) | Catches |
|---|---|---|---|---|
| Injection + PII + toxicity (scanners) | **LLM Guard** | **in-process (CPU)** | input + output | injection, PII leakage, toxic output |
| Grounding | **LLM-as-judge / NLI** | in-process NLI *or* sampled (per measurement) | output | answers not supported by retrieved chunks |
| Injection (classifier) | **Llama Guard** | Ollama — **walk-away / dedicated guard CT only** (not the conversational hot path) | input | prompt injection / unsafe — *comparison validator* |

**First-slice stack = the in-process ones** (LLM Guard scanners + in-process/sampled grounding) on `/context/ask`,
all in shadow. **Llama Guard is a deliberate *comparison* validator** — added once it has a non-evicting venue
(a dedicated guard CT, or run on walk-away paths), so you can A/B its injection verdicts against LLM Guard's on
the same shadow traffic. PII + toxicity are low-value for a single-user lab *enforcement-wise* but earn their
keep as telemetry/learning data.

## Enforcement progression

Everything ships `shadow` → observe verdicts in Grafana → tune → promote per-validator to `flag`/`block` via
config. **No blocking on day one.**

## Scope

**First slice (this implementation):** the pipeline + `guardrail_verdicts` table + Prometheus metrics + the
3 seed validators in `shadow` on `/context/ask` (+ input on `/context/search`).

**Later (not this slice):** grow the stack; promote validators to enforce; then **D** = `act` hook + Hermes
Layer-2 agent guardrails.

**Out of scope (YAGNI):**
- **NeMo Guardrails** → **B32** (Extras); heavy framework + Colang DSL, dialog-oriented — reconsider at Layer 2.
- **`act` tools + agent layer** → **D**.
- **Blocking mode** → only after observation justifies it.

## Risks & open considerations

- **Execution venue & workflow routing (resolved).** A guard call is itself inference, so it routes by B7's
  "is something waiting?" — **walk-away** paths (batch/eval) tolerate model eviction; **conversational** paths
  (`/context/ask` mid-turn) must NOT evict the warm generator. So each validator's config carries an
  **execution venue** + **workflow class**:
  - **Scanners (injection / PII / toxicity → LLM Guard):** run **in-process** in the tool-server (small
    transformers on CPU) — never touch CT 102. Feasible now, no new infra; the default for the conversational
    path.
  - **Grounding (LLM-as-judge):** the only model-contended check. Pick a non-evicting venue by
    **shadow-measurement**: (a) an in-process small **NLI/faithfulness** model (CPU); (b) a small **dedicated
    guard CT** (own always-warm model, isolated — fits the ollama/whisper/hermes pattern); (c) **sampling**
    (judge 1-in-N) or **walk-away-only** grounding on the main Ollama.
  - **NOT in scope — Hardware-Gated → B33:** keeping a *second large* model warm co-resident on CT 102
    (`MAX_LOADED_MODELS≥2`) — the ~48 GB cgroup is already near-full with one 30B-A3B @ 64K. Unlocks with RAM
    headroom (the "weyland box" decision) or the eGPU.
- **Llama Guard via Ollama** is therefore treated as a *walk-away-only* option (or deferred to a dedicated guard
  CT) — it is **not** on the conversational `/context/ask` hot path in this slice; LLM Guard's in-process
  injection scanner covers that.
- **Tool-server weight.** LLM Guard's local HF models (injection/PII/toxicity) add memory + a model-bake layer
  to the tool-server image (like the bge bake). Acceptable, but it grows the pod.
- **Latency stacking → run shadow validators async.** Multiple validators per request add latency even when
  observing. **Refinement:** in `shadow` mode, validators run **async / fire-and-forget** (compute + record the
  verdict, never touch the response) so they add ~zero response latency; only `flag`/`block` modes run
  synchronously (they must, to alter the response). This keeps the observe-and-compare phase free.

## Verification

- **Injection:** send `/context/ask` a query containing an injection attempt → Llama Guard *and* LLM Guard
  produce a `block` verdict *in shadow* (logged, response unaffected) → confirm rows in `guardrail_verdicts`
  + the metric in Grafana. A normal query → `pass`.
- **Grounding:** craft a query whose retrieved chunks don't support a plausible answer → grounding judge
  emits a low score / `flag` verdict in shadow.
- **PII/toxicity:** a query whose answer would surface PII or toxic text → the LLM Guard output scanners flag
  it in shadow.
- **Data product:** `SELECT validator, decision, count(*) FROM guardrail_verdicts GROUP BY 1,2` returns the
  structured telemetry; Grafana panel shows per-validator verdict rates.
- **Non-regression:** with everything in `shadow`, `/context/ask` and `/context/search` behave exactly as
  before (no blocking, only added latency from the validators).
