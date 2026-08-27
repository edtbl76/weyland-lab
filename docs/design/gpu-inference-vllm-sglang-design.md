# On-Demand GPU Inference — vLLM + SGLang (experimentation platform)

## Goal (lab/learning, NOT production)

Stand up **vLLM** and **SGLang** as **on-demand** GPU inference servers on rogueone (RTX 5000 Ada, 16GB), wired into
Bifrost as the `vllm` / `sgl` providers. Two explicit use cases:

- **(b) VRAM-resident throughput experiment** — hold a model in VRAM and feel out **continuous batching / high-throughput**
  serving (the thing Ollama's simpler runner doesn't showcase). Measure tokens/s under concurrency vs Ollama.
- **(c) SGLang's distinct value = PREFIX CACHING (RadixAttention)** — for the lab's agent/RAG workloads (fat repeated
  system prompts / RAG context). A long shared prefix is prefilled once then reused across requests. Measured
  **~6.2× faster TTFT on cache hits (26ms vs 164ms miss)** — `prefix_cache_bench.py`. *(This replaced the original
  "prefill/decode disaggregation" plan — see Rejected below.)*

**REJECTED — prefill/decode (P/D) disaggregation.** The original (c). Killed after verifying: SGLang PD is a **≥2-GPU
architecture** (prefill on GPU 0, decode on GPU 1 via `--base-gpu-id 1`); rogueone has one GPU. The CPU-decode escape
("plan C") is also dead — SGLang's CPU backend is **AMX-only** (Intel Xeon 4th-gen+), and rogueone's **i9-13950HX
(Raptor Lake) has no AMX**; SGLang's shipped CPU+GPU disagg is VLM *encode*-on-CPU, not decode. Real PD = a future 2-GPU
play. The lesson (compute-bound prefill / memory-bandwidth-bound decode) is captured in the demo without running it.

**Non-goals:** always-on production serving; replacing Ollama; single-GPU PD disaggregation. This is a bench, not a service.

## Engine split (match each engine to its strength)

| Engine | Role | Why |
|---|---|---|
| **vLLM** | use case (b) — throughput / continuous batching | Mature continuous-batching; clean OpenAI server; easy to load-test. |
| **SGLang** | use case (c) — **prefix caching** (RadixAttention) | Automatic, aggressive prefix-KV reuse — the distinct edge for repeated-prefix agent/RAG workloads. |

**Three-engine GPU serving (the lab's framing):** **Ollama** = simple single-stream (casual chat, operator brain, judges) · **vLLM** = throughput/concurrency · **SGLang** = prefix caching. Each a distinct job; one bench at a time on the 16GB card.

## On-demand mechanism

rogueone is **not a k8s node** → Docker on rogueone (same pattern as genre-trainer/Ollama). On-demand = **`docker compose
up -d` / `down`** (or start/stop named containers) — **manual trigger** for now (you spin it up when you want to
experiment; it's a bench, not a paged service). NOT `--restart unless-stopped`; NOT always-on. Consequence: the Bifrost
`vllm`/`sgl` providers show **unhappy when the bench is down** — expected and fine. (Future: a wake trigger if it earns one.)

## Models (small — coexist + leave Ollama room)

One or two small models per engine, `Qwen2.5-1.5B-Instruct` / `Qwen2.5-3B-Instruct` class. VRAM hard-capped so a bench run
can't starve Ollama or freeze the desktop (no iGPU): vLLM `--gpu-memory-utilization 0.25`, SGLang `--mem-fraction-static
0.2`, `--max-model-len 8192`. Baseline headroom measured 2026-07-30: ~10.4GB free (desktop + rag-embed ~5.5GB used).

## Bifrost wiring

Both OpenAI-compatible → native providers, base URLs over the LAN (allow-private-network already on from Ollama):
- vLLM → `http://192.168.1.230:8001/v1` (`vllm` provider)
- SGLang → `http://192.168.1.230:8002/v1` (`sgl` provider)
Validate each with the same pull-models → tool-free smoke as the rest of the load-out.

## Phasing

1. **P1 — vLLM throughput bench:** `docker compose up` vLLM (small model, capped) → Bifrost `vllm` provider → tool-free
   smoke → a quick concurrency/throughput measurement (tokens/s at N parallel) as the (b) artifact.
2. **P2 — SGLang prefix-cache bench:** stand up SGLang (normal mode) → Bifrost `sgl` provider → smoke → `prefix_cache_bench.py`
   (shared-prefix cache-hits vs unique-prefix misses, TTFT) as the (c) artifact. (`scripts/sglang-bench.sh` wraps it.)
3. **P3 — capture findings:** a runbook (`docs/runbooks/gpu-inference.md`) with the on-demand start/stop, the smokes, and
   the measured numbers; note the single-GPU disaggregation caveat honestly.

## DoD note

On-demand bench, not a persistent service → **no always-on Kuma monitor required** (it's *meant* to be down); the DoD here
is the **runbook (start/stop + smokes) + the recorded measurements**. GitOps-reproducible via the committed compose file.
