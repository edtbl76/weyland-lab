# Decision models: Jev (TypeSafe AI) and Clef (Cloudflare) (B174, 2026-10-07)

A "System One" decision model returns a typed decision instead of text. You send a **state** (any text or JSON) and
typed **questions** (`choice` over named options, `score` over ordered options, `noul` true/false), and it returns a
probability for every allowed option in one forward pass. TypeSafe AI's **Jev** started the category (2026-09-15).
Cloudflare's **Clef** and **Clef-flash** (2026-10-01) use the same API and are open weights.

## Verdict

| Option | Verdict | Why |
|---|---|---|
| **Jev** (TypeSafe AI) | **DON'T ADOPT — fails the $0 gate.** The owner overrode this for the shadow below (2026-10-07), paid from $25 of prepaid credit, accepting that alert text leaves the LAN | Proprietary and hosted only: `POST https://api.typesafe.ai/v1/systemone`, with no weights, no self-host and no on-prem. $0.042 per million input tokens (output free). The $5 signup credit ended 2026-09-27 ("new signups no longer get free credits"). It is also on Cloudflare Workers AI (`typesafe/jev`) and other gateways at the same per-token price. Whether Workers AI's free 10,000 neurons/day covers it is **unknown**: Cloudflare's pricing page doesn't say, and unknown is not a pass. Every call would also send lab state (alerts, pod names, requests) to a third party. |
| **Clef-flash** (Cloudflare, Apache-2.0, 9B) | **DON'T ADOPT now — measured, no gain at the best-fit seam** | This is the free path, and it runs on rogueone. On the operator's first tool choice (59 labelled cases) it tied the current model: 54 vs 54 correct, median 644 ms vs 687 ms. It also can't replace that model, because it picks a tool name but not the tool's arguments. It needs 8.5 GB of graphics memory in 4-bit, so it can't share the 16 GB card with the operator's model. |
| **Clef** (27B) | DON'T ADOPT | Does not fit the lab's hardware; the model card was tested on one H200. |

**Owner decision (2026-10-07): run both in SHADOW on the incident sweep.** With $25 of TypeSafe credit, the owner
chose to collect evidence on real alerts rather than stop at the 59-case benchmark. After each sweep's agent run, the
operator asks the decision model which tool to open with and counts agreement with qwen's actual first tool:
- **Jev** is the live default, at about $0.0001 a sweep.
- **Clef-flash** is the on-demand alternative on rogueone.

Nothing acts on the answer, so this is evidence-gathering, not adoption. How it runs:
[runbooks/decision-models.md](../runbooks/decision-models.md).

**Re-open when** a lab decision has no LLM in the loop (it needs a typed choice, not tool arguments), or when a larger
card ends the GPU contention (B134/B159). The benchmark below re-runs in about 10 minutes.

## What it is

- **The API.** The request body is `{"model", "state", "questions": {id: {"type", "instructions", "criteria"}}}`. The
  response holds `answers` keyed by question id: a `choice` returns the option, a `confidence` and every option's
  probability; a `score` returns the expected value; a `noul` returns P(true).
- **The vendor claim.** TypeSafe claims up to 200× faster and about 400× cheaper than LLMs on
  classification/decision tasks. Those are vendor numbers. The latency measured here is below.
- **How Clef works.** A Qwen backbone (Clef-flash: Qwen3.5-9B) plus a small "joint schema head"
  (`joint_head.safetensors`, 4 layers). The head reads the backbone's final hidden states and scores every option of
  every question at once. It is custom code (`joint_schema_model.py`), so **Ollama and llama.cpp can't run it**: the
  community GGUF builds hold only the backbone, which generates text and makes no decisions. It runs under
  `transformers` 5.10+.
- **Vendor-published scores** (the Clef model card's "Decision Index", not lab measurements):
  - Clef-flash vs Jev: BFCL 98.8 vs 95.8; API-Bank 93.1 vs 88.2; median latency 38.8 ms vs 524.1 ms on Cloudflare's GPUs.
  - Jev leads on reasoning: GPQA Diamond 78.3 vs 51.0; BBH 92.9 vs 68.9.

## Constraint gate (settled first)

| | Jev | Clef-flash |
|---|---|---|
| Hosting | TypeSafe cloud API; also on Workers AI, OpenRouter and other gateways. No weights. | Open weights on Hugging Face (`Cloudflare/clef-flash`, 19 GB bf16); also on Workers AI |
| Price | $0.042 / M input tokens, output free. No free tier for new accounts since 2026-09-27. | $0, self-hosted (Workers AI: $0.09 / M input) |
| License | Proprietary (TypeSafe Master Customer Agreement) | Apache-2.0 |
| Data | Leaves the LAN. TypeSafe says it doesn't train on customer data; zero retention is Enterprise-only. | Stays on rogueone |
| $0 gate | **FAIL** (the Workers AI free allowance is unknown) | **PASS**, if it fits the hardware (measured below) |

## Per-seam overlap

| Seam | What decides today | Call | Why |
|---|---|---|---|
| **Operator tool choice** (B66) | `qwen2.5:7b-operator` on rogueone, 21 curated tools | **skip** (measured) | It tied the current model on accuracy and median latency. The operator still needs an LLM to write the tool's arguments (namespace, PromQL, SQL), so Clef would add a model rather than replace one, and it can't share the card with that model. |
| **weyland-guard verdict** (B70/B115/B117) | Purpose-built classifiers: Prompt Guard 2 (DeBERTa), Presidio, NLI DeBERTa, Llama-Guard-3-1B on CPU | **skip** | Each validator is a small specialist with its own published safety evaluation. Clef has no safety-taxonomy benchmark beyond phishing (PhishNChips 75.0, below DiffusionGemma Jev's 85.4). The guard runs on mother's CPU, and Clef-flash couldn't finish one request in 12 minutes on rogueone's CPU (below), so it is no answer to Llama Guard's 8.6 s. |
| **MCP `policy.gate`** (B17/B19) | Deterministic identity, allowlist and rate limit | **skip** | An access-control gate must be deterministic and auditable. A probabilistic model there would be a regression. |
| **Eval classifiers / judges** (B84/B96, Langfuse) | LLM judges (`wl-judge`, `wl-judge-oss`) | **skip** | B190 found that text-only quality scores did not predict outcomes (AUC ~0.51, [issue-readiness.md](issue-readiness.md)). A cheaper scorer of the same kind does not fix that. |

## Micro-benchmark: the operator's first tool choice (2026-10-07, rogueone)

- **The decision.** Given a request, which ONE of the operator's 21 local tools should be called first?
  (`delegate_to_realm` is dropped for sweep cases, as in production, where the sweep runs without it.)
- **The cases (59).** Each lists every tool that would be a correct first move. The labels were written before either
  model ran.
  - **23 real incident-sweep prompts:** one per distinct alert name the operator was handed between 2026-09-07 and
    2026-10-07 (548 sweeps).
  - **6 real chat requests**, from the MLflow `operator` traces and Postgres `operator_sessions`.
  - **30 written requests** in the same style, two per tool.
- **Baseline (the current path).** The production first step, with the system prompt and tool schemas copied from a
  live MLflow trace: `qwen2.5:7b-operator` through Ollama, temperature 0, `max_tokens` 256.
- **Clef-flash.** The same decision as one `choice` question whose options are the tool names, each described by its
  tool description; the state is the operator's rules plus the request.

| | Correct | Real sweeps | Real chat | Written | Median | p95 |
|---|---|---|---|---|---|---|
| qwen2.5:7b-operator (current, GPU) | **54/59** | 22/23 | 6/6 | 26/30 | 687 ms | 2,445 ms |
| Clef-flash, 4-bit NF4 (GPU, 8.5 GB peak) | **54/59** | 19/23 | 6/6 | 29/30 | 644 ms | 677 ms |
| Jev `jev-1.13.0` (TypeSafe API, from rogueone) | **53/59** | 18/23 | 6/6 | 29/30 | 166 ms | 204 ms |
| Clef-flash, bf16 (CPU, 12 cores) | not measured | | | | > 12 min | |

- **Jev's run was paid from the owner's $25 TypeSafe credit (2026-10-07).** It used 119,076 input tokens, about
  $0.005, or roughly $0.00008 per decision. Jev missed 5 node memory and disk alerts, sending them to
  `k8s_events_list`, and one written realm request, which it sent to memory search.

- **Repeatability.** Clef-flash is deterministic: two runs made the same 59 picks. qwen is not: at temperature 0, two
  runs disagreed on 3 of 59 picks, and the first scored 53.
- **Clef can't run on CPU here.** Its warm-up request had not finished after about 12 minutes on rogueone's 12 cores,
  using the slow reference kernels. So it is not a CPU (mother) candidate.

**How each model missed:**
- **qwen** confused `context_ask` with `context_search` (2) and `context_search` with `memory_search_notes` (1). It
  returned no tool for "list the CronJobs", and chose Prometheus for one job alert.
- **Clef** sent four metric alerts to Loki logs: disk ×2, major page faults, and Bifrost spend.

**Confidence is the one real advantage:** every Clef answer with confidence ≥ 0.5 was correct (38/38); its misses sat
at 0.27-0.47. That supports TypeSafe's "confidence-gated routing" pattern: act on a confident decision, hand the rest
to an LLM.

**Limits:**
- n = 59, labelled by one author.
- Clef ran with the slow reference kernels (`causal-conv1d` and `flash-linear-attention` not installed), so its GPU
  latency is pessimistic.
- 4-bit loading is not the configuration Cloudflare tested.

**The benchmark disturbed the live operator.** While Clef held the GPU, Ollama reloaded the operator's model with
0.88 of its 6.8 GB on the card. The CPU run then took the cores, so live operator requests failed at their 60 s
timeout. The cost was one incident sweep that errored (`operator_brain_selected_total{brain="none",
reason="local_error"}`), with no paid failover. The fix was to unload the model and reload it (6.59 of 6.59 GB on the
card). This is the GPU-contention cost any second model on the 16 GB card would carry.

**A side finding:** with no output cap, the qwen baseline once generated about 20K tokens for `KubePodNotReady`
instead of calling a tool. That held Ollama for 5 minutes and failed three live operator requests at their 60 s
timeout. The live operator sets no `max_tokens` either; it relies on `OPERATOR_LOCAL_TIMEOUT` (60 s).

**The production record agrees** that tool choice was not the problem:
- Before the 2026-10-03 context-window fix, sweeps called no tool 293 times out of 542 and the knowledge base 219
  times. That came from Ollama silently cutting the prompt.
- Since the fix, 5 of 6 sweeps open with a live-state tool.

Reproduce: [`eval/decision-model/`](../../eval/decision-model/README.md).

## Integration shape (built 2026-10-07 as a shadow)

- **A client inside the operator, not a new service.** `decide.py` speaks the Jev API, so Jev and Clef-flash differ
  only by URL and model name. A standalone `wl-decide` service was considered and not built: it would have had no
  consumer, and an always-on Clef would hold the GPU the operator's model needs.
- **Clef-flash runs on demand.** `clef-flash/server.py` wraps Clef's own `systemone()` helper on rogueone `:8004`,
  through `scripts/clef-flash.sh`.
- **Not an MCP tool:** a decision model is called by code, not chosen by an agent.
- **Not inline in weyland-guard:** that service runs on mother's CPU, and a 9B model is the wrong size for it.
