# LLM Inference — CPU vs GPU Tradeoffs (the *why*)

Generalizable background for model-serving hardware decisions: capacity vs speed, why token
generation is memory-bandwidth-bound, when CPU vs GPU each make sense, and the tiered-inference
pattern. Pulled out of the B7 decision doc so it stands on its own and outlives any one purchase.

**Related:** [B7 — Model Serving Hardware (the decision)](b7-model-serving-hardware.md) ·
[Ollama runbook + measured benchmarks](b7-ollama-runbook.md).

---

## The inference tradeoff

### Two independent axes
- **VRAM/RAM = capacity = *what* you can run.** A **hard wall**: weights + KV cache must fit, or
  it won't load (or spills to slow CPU offload). 24 GB clears 30B@4-bit; 48 GB clears 70B@4-bit.
- **Memory bandwidth = speed = *how fast* once it fits.** A **dial**, not a wall.

### Why token speed is bandwidth-bound
Generating each token reads **every weight once**, so **tokens/sec ≈ bandwidth ÷ model-size**.
A 30B@4-bit (~18 GB) on a 3090 (936 GB/s) ≈ 936÷18 ≈ 52 theoretical (~25–40 real). CUDA cores
barely affect *generation* — they affect **prefill** (digesting the prompt), the other half of
latency. **Quantization moves both axes**: 70B 8-bit→4-bit both *fits smaller* and *runs ~2×
faster* (half the bytes per token). Q4 ≈ sweet spot; below Q3 quality degrades.

> **Measured corollary (CPU):** the 1/N "active-params" law is confirmed on weyland — see the
> [measured-benchmark table](b7-ollama-runbook.md#measured-benchmarks). On CPU, MoE models read only
> their *active* experts per token, so a 30B-total / 3B-active MoE runs at ~3B *speed* with ~30B
> *capability* — the key to "big models, usable speed" without a GPU.

### GPU vs CPU are opposite corners — the economic core
**VRAM is fast + expensive; RAM is slow + cheap (~50–100×/GB).** So: buy a *little* fast memory
(GPU) for what runs **constantly/interactively**, lean on *lots* of cheap slow memory (CPU) for
what runs **occasionally/in bulk**. Same logic as cache vs RAM vs disk.

| | Capacity | Bandwidth | Best for |
|---|---|---|---|
| **GPU** | small (16–48 GB VRAM) | high (576–1800 GB/s) | **fast & fits**: interactive, long-prompt/prefill, high-volume |
| **CPU** | large (96 GB+ RAM) | low (~85 GB/s DDR5) | **big or batch**: too-big-for-VRAM, latency-tolerant, occasional |

### When each makes sense (workload routing — applies anywhere)
**GPU when:** a human / tight agent loop is **waiting** (latency compounds across turns) · long
prompts / RAG / big code context (prefill is compute-bound — CPU can take *minutes* on 30K
tokens) · high concurrency/batching · the model **fits VRAM** and speed matters at all.
**CPU when:** the model **doesn't fit VRAM** (the capacity escape hatch — run 70B+ that no
affordable GPU holds) · **nothing is waiting** (overnight eval, bulk processing, async steps) ·
you need the big model **rarely** (don't justify GPU capex) · embeddings/small models that are
"fast enough."

**Decision as gates:** (1) Fits VRAM? No → CPU/offload. (2) Something waiting? Yes → GPU.
(3) Long prompts / high volume? Yes → GPU.

**Middle ground — hybrid offload:** llama.cpp can split a model *N layers on GPU, rest on CPU*
— for a model that *almost* fits (70B on 24 GB). Speed lands between the two, bottlenecked by
the CPU half. The "make it fit, claw back some speed" lever.

### The pattern this produces (tiered inference)
> Run a **fast, fits-in-VRAM model as the interactive daily driver on GPU**, and keep a
> **bigger, smarter model on CPU for the occasional latency-tolerant "max capability" call.**
> Route by *"is someone waiting?"* and *"does it fit?"* — **not** by which model is "best."

An **agent harness is exactly this workload**: most steps are quick reasoning/tool-calls (GPU),
with the occasional hard problem worth waiting on (CPU). Which is why weyland's CPU/Ollama path
(capacity) + a future 24 GB eGPU (speed) is a *complete* answer, not a compromise — each axis
covered by the corner that's cheap at it. The 48 GB premium buys capacity you *already have* on
the CPU, not speed (A6000 bandwidth ≈ a 24 GB card), so it only pays off if you need 70B **fast
and often** — uncommon for harness dev.

### Lab context — weights everything above
**This is a homelab for experimentation/learning, not production.** That softens the "is someone
waiting?" gate *across the board* — there's no SLA, you're usually the only user, and you're
poking at models to learn. Consequences:
- **CPU/Ollama covers more than it would in prod** — slow is fine when nothing's waiting; 70B at
  ~1–2 tok/s is genuinely useful for a lab. The committed CPU path is *enough* for most work.
- **The eGPU is quality-of-life, not required** — it makes the interactive loop pleasant; no
  experiment is blocked without it. Add it when a workload actually annoys you, not preemptively.
- **Don't over-spend / over-engineer:** a used 3090 (24 GB) is peak-homelab; $3k+ workstation
  cards (A6000/6000 Ada) are production economics — skip unless a specific experiment needs
  fast-70B. The CPU "slowness" is itself instructive (teaches bandwidth/quant tradeoffs).

## Performance envelope — expected tok/s (ballpark, Q4)

> **Measured numbers now live in the [Ollama runbook](b7-ollama-runbook.md#measured-benchmarks).**
> The tables below are the *conceptual* ballpark and the reasoning behind them — kept for the
> "why," superseded by real data for the "what."

weyland CPU ceiling ≈ **~70–80 GB/s** DDR5 (dual-channel ~5600). Reading speed anchor ≈ 7–10 tok/s.
These were estimates *before* benchmarking — note the real MoE numbers beat the dense estimates
because MoE only pays for active params.

| Model (Q4) | Size in RAM | weyland **CPU** gen | Feel (CPU) |
|---|---|---|---|
| 7–8B | ~5 GB | ~10–14 tok/s | real-time, fine interactively |
| 14B | ~9 GB | ~6–8 tok/s | just under reading speed — usable |
| 32B | ~20 GB | ~3–3.5 tok/s | slow; non-interactive |
| 70B | ~42 GB | ~1.5–2 tok/s | kick off & walk away (batch/async) |

**Hidden cost = prefill (prompt digestion), not generation.** Prefill is compute-bound; on CPU a
long prompt (big RAG context, several code files) adds **tens of seconds → minutes** before the
first token. Negligible for short prompts; the main pain for long ones. (A GPU fixes this most.)

### CPU vs GPU — same model, the ~10× gap (and where the GPU *doesn't* help)
| Model (Q4) | weyland **CPU** | **24 GB** 3090 | **48 GB** A6000 |
|---|---|---|---|
| 8B | ~12 tok/s | ~100+ | ~80+ |
| 14B | ~6–8 | ~60–80 | ~50 |
| 32B | ~3 | ~30–40 | ~25–30 |
| 70B | ~1.5–2 | ❌ doesn't fit → offload, ~3–5 | ~10–15 |

- **For models that FIT, the GPU is ~10× on gen + far more on prefill** (32B: ~3 → ~35 tok/s =
  batch-tool → interactive). Not marginal.
- **The "GPU barely helps" case is exactly one: 70B on a 24 GB card** — doesn't fit, spills to
  CPU, lands back near CPU speed. A 24 GB card transforms ≤32B; only a 48 GB card makes 70B fast.
- **Two different comparisons:** "~1.6×" was 3090 vs the *laptop GPU*; vs weyland's **CPU** (where
  it runs today) a 3090 is **~10×**. weyland is CPU-only now → the 10× is the relevant figure.
- **Lab reconciliation:** CPU is *sufficient* (nothing blocked), but the GPU is a real ~10×
  *experience* upgrade for 8–32B. "Not needed" ≠ "not impactful." Size the card to a model that
  fits it (24 GB → 32B); 70B-fast (48 GB) is the rare thing a lab seldom needs.

## Runtime note (engine follows the hardware)
- **GPU path → vLLM** (preferred — PagedAttention, OpenAI-compatible API).
- **CPU path → llama.cpp / ollama** (GGUF quant fits big models in RAM; also serves an
  OpenAI-compatible `/v1` API, so harness code is engine-agnostic). vLLM *has* a CPU backend
  but it's immature and fp16-leaning (70B won't fit 96 GB) → **not** recommended for CPU.
