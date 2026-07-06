# B2 — Agent Platform (Hermes + OpenClaw) — Design

**Status:** Scoped 2026-06-13 (design approved; first slice not yet built).
**Goal:** Give the lab a conversational **"view into the system"** through autonomous agents — query
knowledge, watch health/observability, and (later) drive workflows — without data leaving the LAN.

This doc captures the architecture and the decisions (with rationale) reached while scoping B2. It is the
reference for the build slices that follow.

---

## 1. The two agents — complementary, not competing

We run **two** agent runtimes, deliberately. They are **complementary specialists**, not redundant
assistants — which is what makes "have both" a strategy rather than indulgence.

| | **Hermes** (NousResearch/hermes-agent, MIT) | **OpenClaw** (v2026.5.31, on the `openclaw` VM) |
|---|---|---|
| **Lane** | **Primary** — autonomous system-view / ops workhorse **and the single front door** | **Contained delegate** — tapped for skill breadth / extra channels |
| **Strength** | Always-on, learns recurring tasks, self-improving skills, **Python-native + strong local-inference fit**, lean & **stable** | Multi-agent orchestration, multi-channel comms, **thousands of community skills**, Node.js I/O-heavy gateway |
| **On the critical path?** | **Yes** — front door + daily driver | **No** — its breakage must never block the way in |

### Why Hermes is primary (and on the critical path)
Not because it's a superset — they're orthogonal — but on **stability + local-inference fit**. For an
always-on homelab system-view agent you want the lean, doesn't-break-on-update one at the front door.

### Why OpenClaw is off the critical path
We have **firsthand evidence OpenClaw is the fragile one**: during the B11/B13 work it broke its gateway
**twice** (`tools.media.audio` rejected → fails closed; `openclaw doctor --fix` clobbered `gateway.mode`).
The comparison literature's "prone to breaking during platform updates" is, for us, a logged outage. You
never put the component you've watched fail at the single entry point. OpenClaw's durable value is its
**skill library + channel reach** — things you reach *for*, not things that must be *up*.

---

## 2. Architecture — three layers, one seam

```
            ┌─────────── chat channel (single front door) ───────────┐
            ▼
   ┌─────────────┐   MCP    ┌──────────────────────┐   REST   ┌───────────────┐
   │   Hermes    │─────────▶│  Weyland system-view  │─────────▶│  tool server  │
   │ (primary,   │          │      MCP server       │          │ (RAG, status, │
   │  isolated   │          │  (ONE server, both    │          │  pipelines,   │
   │     CT)     │◀────┐    │   agents consume)     │          │  observ., …)  │
   └──────┬──────┘     │    └──────────────────────┘          └───────┬───────┘
          │ gateway    │ MCP                                          │
          │ (deferred) │    ┌──────────────┐                          ▼
          ▼            └────│   OpenClaw   │                  Ollama /v1 + Qdrant/
   ┌─────────────┐         │  (delegate)  │                  Weaviate/Neo4j/PG +
   │  OpenClaw   │         └──────────────┘                  Prometheus/Dagster
   └─────────────┘
          ▲ both agents' model backend ──▶ Ollama /v1 (192.168.1.244:11434)
```

Three wires, in priority order:

1. **Brain (inference)** — both agents' model backend → **Ollama `/v1`** (`192.168.1.244:11434`). Hermes via
   `hermes model`; OpenClaw via its provider config. "Your own endpoint" path — no cloud keys, nothing
   leaves the LAN.
2. **Eyes & hands (the system view)** — both agents → the **Weyland system-view MCP server**, which fronts
   the existing **tool server**. This is the heart of the "view into the system" goal.
3. **Collaboration & front door (deferred)** — Hermes on a chat channel = the single entry point; Hermes
   calls OpenClaw's gateway **as an MCP tool** when breadth helps (topology 3, asymmetric).

### Why the system view is a *platform* capability, not an agent feature
The view lives in the **tool server / MCP**, consumed equally by both agents — never baked into one. Two
consequences:
- **Co-location buys nothing.** Both agents see the *identical* view whether they share a host or sit at
  opposite ends of the LAN. So isolation (below) costs zero "shared system-ness."
- **The single entry point is a front-layer concern, not a host concern.** It's independent of where the
  agents run.

### Why MCP is the seam
Hermes supports MCP ("connect any MCP server"); OpenClaw's MCP support is to be confirmed at its wiring
slice. Building the system view **once** as an MCP server turns integration from **N×M into N+M**: write
Weyland's view once, each agent (now and future) adds one line to register it — instead of hand-building
Weyland skills inside every agent separately.

---

## 3. Hosting & isolation

**Hermes runs in its own isolated LXC CT** (sibling to the Ollama CT 102 / whisper CT 103), **not**
co-located with OpenClaw, and **not** on `mother`.

Rationale: Hermes does **sandboxed code execution, browser automation, and reads untrusted web content** —
the exact attack surface B14 (Guardrails) exists for. Isolation bounds the blast radius of a compromised or
prompt-injected agent. `mother` is the platform/data plane and is disqualified outright; co-locating two
code-executing agents on the `openclaw` VM would merge their blast radius for no benefit (the shared view is
already at the platform layer).

---

## 4. v1 scope — read-only "observe"

The first slice is **read-only**: the agent can *tell* you about the system but cannot change it.

- **In v1:** query knowledge (RAG: `/context/ask`, `/context/search`), health/status (`/status`,
  per-backend health), observability (PromQL proxy + recent alerts — B5 made these real).
- **Not in v1:** any side-effecting action (triggering Dagster, evals, restarts).

Rationale: prove the whole loop (agent → MCP → tool server → system) safely. A read-only agent has **zero
blast radius even if a model misfires or gets prompt-injected** — so we de-risk the mechanics before adding
power. Promotion to **read + act** is a later slice, gated on **B14 guardrails** being in place (an agent
that reads untrusted content *and* can fire pipelines is precisely what B14 guards).

---

## 5. Protocol: MCP now, A2A as a gated future (→ B17)

**MCP for everything now, including the OpenClaw bridge.** A2A (Agent2Agent) is **not** a competitor to MCP
— they're complementary:

- **MCP = agent ↔ tools/context.** Other end is a capability provider. Request/response. *Acting on the
  system is always this* — even side-effecting actions are agent→tool, not agent→agent. **A2A is never
  required to act on the system.**
- **A2A = agent ↔ agent.** Other end is an autonomous peer — discovery (Agent Cards), task lifecycle,
  streaming, long-running delegation, negotiation.

Our designed relationship (asymmetric: Hermes primary, OpenClaw a *bounded* delegate; symmetric peering
*rejected*) is **tool-shaped**, so MCP models it perfectly: wrap OpenClaw's gateway behind a thin MCP server
(`ask_openclaw`, `run_openclaw_skill`). Keeping the whole stack on **one protocol Hermes already speaks**
means one mental model and one chokepoint for B14 guardrails.

**A2A earns its place only when** (any of): (a) we want true symmetric peer collaboration; (b) a **third+
powerful agent** joins that needs discovery/coordination — this is the real trigger, arriving with **B15
(opencode + Cline)** as the agent fleet grows capable; (c) one platform ships A2A natively (making the
semantically-correct option nearly free). The pull is specifically **long-running, async, autonomous
cross-agent delegation** — not "the agent gained write access." Even then, **A2A sits alongside MCP on the
one agent↔agent edge; MCP is never replaced, and nothing built now is wasted.** Tracked as **B17**,
sequenced with B15.

---

## 6. Open items to validate (before/during the build)

1. **Local-model tool-calling reliability.** MCP + function-calling are confirmed for Hermes, but **not
   specifically with Ollama models** — and local tool-calling quality varies a lot by model. Smoke-test
   that our tool-capable models (`qwen3-coder:30b`, `qwen3:30b-a3b`, `mistral-small3.2:24b` all advertise
   tools) actually fire an MCP tool through Hermes **before** building much on top.
2. **Agent model — DECIDED 2026-06-13: `qwen3-coder:30b` (measured + validated).** Started with
   `mistral-small3.2:24b` (non-thinking, B4-proven structured output) — but it's **dense 24B → ~30 tok/s
   prefill on CPU**, which made turns multi-minute. Switched to `qwen3-coder:30b` (**30B-A3B MoE, ~3B active
   params**) and measured the difference: **~4.4× faster prefill** (154 vs 35 tok/s @ 1k tokens), **no
   `<think>` blocks** (the qwen3 *thinking* models' empty-output risk doesn't bite the Coder variant), and
   **tool-calling validated** — it fired the `terminal` tool and returned real `uname -a` output, not a
   hallucination. It's also the agentic/tool-tuned variant, so it's the right brain on *both* speed and
   capability. `gpt-oss:20b` remains the B4 RAG pick — a separate axis. **Key lesson: on CPU, *active* params
   (MoE), not total size, set speed — the "bigger" 30B beat the 24B by 4.4×.**
3. **OpenClaw MCP support** — confirm at the (deferred) OpenClaw-wiring slice.
4. **Chat channel — DECIDED 2026-06-13: Telegram, via a NEW dedicated bot** (separate from
   `@weyland_alerts_bot`). One channel for v1. Rationale: lowest-friction proven path in this lab (BotFather);
   a distinct bot keeps two-way agent conversation out of the one-way alert firehose, and coexists fine with
   OpenClaw's Telegram presence. Token lives in the CT's `~/.hermes/` config (not in the repo → out of git).
   More platforms can be added later, but v1 is Telegram-only.

---

## 7. First-slice build sequence (read-only v1)

1. Provision an isolated **`hermes` LXC CT** on weyland; install Hermes (`install.sh`); `hermes setup`.
2. Point Hermes's model backend at **Ollama `/v1`**; validate basic chat.
3. **Validate tool-calling** with the candidate models (open item #1) — pick the agentic model.
4. Build a minimal **Weyland system-view MCP server** fronting the tool server — start with **RAG + status**;
   add **observability (PromQL/alerts)** next.
5. Register the MCP server in Hermes; wire **one chat channel** as the front door.
6. Validate end-to-end: ask Hermes a system question → it calls an MCP tool → answers from live state.
   **Also verify the effective context window here** (this is where truncation shows up): agent loops
   accumulate system prompt + tool defs + tool results + history fast. The effective window is gated by
   **Ollama's `num_ctx` on CT 102**, *not* the model's ~128k max or Hermes's setting — if the agent silently
   "forgets" earlier context, raise `num_ctx` (Modelfile or request options) to ≥16k–32k.

**Deferred slices:** OpenClaw MCP registration · Hermes→OpenClaw delegation (topology 3) · read+act
promotion (gated on B14) · A2A evaluation (B17) · **Anthropic (or other cloud) as an optional *secondary*
provider** — a "use the smarter model for hard problems" escape hatch via `hermes model`. **Opt-in, never the
default**: it departs from local-only (system state would leave the LAN + per-use cost), so it's a conscious
per-task choice, not the standing brain.

---

## 8. Decision log

| Decision | Rationale |
|---|---|
| Run **both** Hermes + OpenClaw | Complementary specialists (autonomous doer vs connector/orchestrator), not redundant. |
| **Hermes primary** + front door | Stability + local-inference fit; the lean always-on one belongs on the critical path. |
| **OpenClaw off critical path** | Firsthand fragility (gateway broke twice this session); value is skill breadth/channels, reached *for* not depended *on*. |
| **System view = platform/MCP**, not in an agent | Identical view for all agents; decouples "shared view" from host placement. |
| **One MCP server**, both consume | N+M not N×M integration; future agents add one registration line. |
| **Hermes in its own isolated CT** | Code-exec + untrusted-content blast radius; `mother` disqualified; no benefit to co-locating two executors. |
| **Read-only v1** | Prove the loop with zero blast radius; promote to act only behind B14. |
| **MCP for the OpenClaw bridge too** | Relationship is asymmetric/tool-shaped; one protocol, one guardrail chokepoint. |
| **A2A deferred → B17, with B15** | Gated on async peer-delegation / a powerful multi-agent fleet; additive to MCP, never a replacement. |
| **Local Ollama is the brain; cloud (Anthropic) is opt-in only** | Always-on agent with system access shouldn't ship infra state off-LAN or incur per-use cost by default; cloud is a conscious per-task escape hatch via `hermes model`, never the standing default. |
| **Agent model = `qwen3-coder:30b`** (was mistral-small3.2:24b) | Dense 24B mistral = ~30 tok/s prefill on CPU (multi-min turns). `qwen3-coder` is 30B-A3B **MoE** → *measured* ~4.4× faster prefill (154 vs 35 tok/s), no think-aloud, tool-calling validated (real `uname -a`). MoE *active* params, not total size, set CPU speed. `gpt-oss:20b` stays the B4 RAG pick (separate axis). |
| **Ollama CPU tuning for the agent (CT 102)** | `OLLAMA_CONTEXT_LENGTH=65536` + `OLLAMA_KEEP_ALIVE=-1`. Prefix caching works (turn-2 prefill 111 tokens vs ~17k base) **but is fragile**: `OLLAMA_MAX_LOADED_MODELS=1` means any other model request (RAG/WebUI/evals) evicts qwen3-coder and kills its cache → next agent turn pays full cold prefill. Don't churn Ollama. |
| **Context window = 64K (`65536`), Hermes==Ollama** | Model's native 262K is off the table on CPU — KV cache ~165 MB/1k tokens → 262K ≈ 58 GB → OOMs the 48 GB cgroup; 64K ≈ 25 GB, fits, leaves ~47K above the 17K base prompt. Hermes auto-detects the native 262K (via `model_catalog`) and silently truncates past what Ollama serves unless `context_length` is pinned to match (and `model_catalog` disabled if it overrides). |
| **MCP transport = HTTP (Option A confirmed 2026-06-13)** | Hermes supports remote **HTTP** MCP servers (`mcp_servers:` block, `url` key, optional `headers`/`auth: oauth`/mTLS) — not just stdio. So we build **one** HTTP MCP server fronting the tool-server and *both* agents connect by URL (the N+M design), rather than a per-agent stdio adapter. |
| **Toolset size is a no-op — `tool_search` is on** | *Measured bidirectionally* (disable skills→0, disable vision→0, enable spotify→0): tools live in a searchable registry, **not** the system prompt. The ~17k context is Hermes's irreducible **base framework prompt**, not tool schemas. So enable any *functional* tool freely (cost-free); the only reason to disable a tool is if it can't function (no backend). There is no "trim tools for speed" lever. |

---

## Related
- **[../runbooks/agent-hermes.md](../runbooks/agent-hermes.md):** operational runbook — CT creation, install, config, model + Ollama tuning, slash-command management, and the bring-up gotchas (PATH, context mismatch, `tool_search`, caching).
- **B14 — Guardrails:** gates the read→act promotion; prompt-injection awareness once agents read untrusted content.
- **B15 — opencode / Cline:** the powerful-agent expansion that triggers the B17 A2A evaluation.
- **B17 — A2A evaluation:** the agent↔agent protocol decision (see backlog).
- Platform context: [../arch.md](../arch.md) · endpoint inventory: [../api.md](../api.md) · hosts: [../hosts.md](../hosts.md).
