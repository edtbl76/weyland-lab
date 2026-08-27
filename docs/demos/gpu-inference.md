# Demo — On-Demand GPU Inference: three engines, three jobs

**What this demonstrates:** the lab has **three GPU serving engines**, each with a *distinct* job on rogueone's RTX 5000
Ada (16GB) — not redundant, purposeful:

| Engine | Job | The measured win |
|---|---|---|
| **Ollama** | simple single-stream (casual chat, operator brain, judges) | the always-on default |
| **vLLM** | **throughput / continuous batching** (concurrent + batch workloads) | **~15× tok/s** at concurrency 16, flat latency |
| **SGLang** | **prefix caching** (RadixAttention) for agent/RAG (fat repeated prompts) | **~6.2× faster TTFT** on cache hits |

Both vLLM and SGLang are on-demand (spun up per experiment, one at a time), fronted by Bifrost. This demo explains **both
wins from the silicon up**. *(We also explored SGLang prefill/decode **disaggregation** and rejected it — it needs ≥2
GPUs; see the runbook.)* B111 use cases (b) + (c).

Design: [gpu-inference-vllm-sglang-design.md](../design/gpu-inference-vllm-sglang-design.md) ·
Runbook: [runbooks/gpu-inference.md](../runbooks/gpu-inference.md) · Compose + benches:
`nodes/rogueone/services/gpu-inference/` · scripts `scripts/vllm-bench.sh`, `scripts/sglang-bench.sh`.

---

# Case 1 — vLLM: continuous batching (use case b)

---

## The measured result (the artifact)

`python3 nodes/rogueone/services/gpu-inference/bench.py` — 128-token generations fired at concurrency 1/4/8/16, **direct
at vLLM** (`localhost:8001`, not through Bifrost, to measure the *engine*):

```
 conc  out_tok  elapsed_s     tok/s  avg_lat_s
    1      128       1.44      88.9       1.44
    4      512       1.41     363.0       1.40
    8     1024       1.38     742.3       1.37
   16     2048       1.54    1329.5       1.52
```

Two numbers matter, and they matter *together*:

- **`tok/s` went up ~15×** (88.9 → 1329.5) as concurrency went 1 → 16.
- **`avg_lat_s` stayed essentially flat** (1.44 → 1.52s).

Flat latency while throughput scales linearly means **the 16 concurrent requests all completed in roughly the same
wall-clock time as a single request did.** The GPU served 16 users for almost the price of 1. Everything below explains
*why that is physically possible* — it is not a trick, it falls out of how transformer decoding uses the hardware.

---

## Why this happens — from the silicon up

### 1. LLM inference is two completely different workloads: prefill and decode

Every completion has two phases with **opposite hardware characteristics**:

- **Prefill** — the model reads your entire prompt *at once* and builds the KV cache, emitting the first output token.
  This is one big matrix-multiply over all prompt tokens → **compute-bound**: the GPU's tensor cores are busy, memory
  bandwidth is not the bottleneck. Prefill is fast and efficient per token because there's lots of parallel math.

- **Decode** — the model then generates output tokens **one at a time**, autoregressively. To produce token N it feeds
  token N-1 through all the layers, produces token N, appends it, repeats. This is **memory-bandwidth-bound**, and that
  fact is the entire story.

### 2. Why single-stream decode wastes the GPU (the conc=1 row)

To generate **one** token in decode, the GPU must **read every weight in the model out of VRAM**. For our 7B AWQ that's
~5.5GB of weights streamed from VRAM through the compute units — to do a tiny amount of actual math (one token's worth)
and throw the weights away. Then it does it *again* for the next token.

So at concurrency 1, the bottleneck is **VRAM bandwidth**, not compute. The tensor cores — the expensive part of the GPU —
sit mostly **idle**, starved, waiting on memory. `88.9 tok/s` is the card reading its own weights over and over for a
single conversation. Most of the silicon is doing nothing.

### 3. Why batching is nearly free (the conc=16 row)

Here's the key insight: **the weights are shared across all requests.** Reading those 5.5GB of weights out of VRAM
produces one decode step — but that *same single read* can drive the decode step for **1 request or 16 requests at once**.
The weights don't change per user; only the small per-request state (the current token + that request's KV cache) differs.

So batch 16 requests' decode steps together and you get **16 tokens out of one 5.5GB weight-read** instead of 1. The
expensive, bandwidth-limited part (streaming weights) is **amortized across the whole batch**. The previously-idle tensor
cores now have real work — 16 tokens' worth of math per weight-read instead of 1. In roofline terms, batching raises the
**arithmetic intensity** (math-per-byte-read), sliding the workload off the memory-bound wall toward the compute roof.

That is why `tok/s` scales ~linearly with the batch: **88.9 × 16 = 1422 ideal, we measured 1329.5 → ~93% efficiency.**
We were nowhere near saturating compute at 16; almost all the gain was pure amortization of the weight-read.

### 4. Why latency stays flat

A single request still needs exactly **128 decode steps** (128 forward passes) to emit 128 tokens — batching does **not**
add steps to any one request. It runs *more requests in parallel per step*. So one request's wall-clock — 128 steps ×
per-step time — is unchanged **as long as per-step time doesn't grow**. Early on it doesn't (the step was memory-bound and
had idle compute to spare), so latency holds at ~1.4s.

You can already see the **first hint of the knee** at conc=16: `avg_lat_s` crept 1.37 → 1.52s. That's per-step time
starting to rise as the batch begins to press on compute / KV bandwidth. Push concurrency higher and eventually latency
climbs steeply while tok/s flattens — that's the **saturation point** (the roofline ridge). We stopped just before it.

### 5. What makes it *"continuous"* batching specifically

Two more mechanisms make this practical, both from vLLM:

- **Continuous (a.k.a. in-flight / iteration-level) batching** — vLLM re-forms the running batch at **every decode step**:
  a request that just finished *leaves* the batch and a waiting request *joins* mid-flight, without waiting for the whole
  batch to drain. Naive "static" batching would make a 5-token request wait for a 500-token request in the same batch,
  wasting the GPU. Continuous batching keeps the batch **maximally packed every single step**. (Our bench uses equal-length
  requests, so we don't *see* the ragged-length win here — but it's the same scheduler doing it.)
- **PagedAttention** — vLLM stores each request's KV cache in **non-contiguous fixed-size blocks**, like OS virtual-memory
  paging, instead of one padded contiguous buffer. No memory wasted on padding/fragmentation → **more concurrent requests
  fit in the same 16GB**, which is what lets the batch get big enough to amortize the weight-read in the first place.

---

## Why this matters for the lab (vs Ollama)

Ollama is perfect for **one conversation at a time** — but it doesn't showcase this. The moment the lab wants **concurrent
or batch inference** — a judge panel scoring 200 eval rows, labeling a dataset, many agents at once — a serial-ish runner
serves them roughly one-at-a-time near that lonely **88.9 tok/s**, while vLLM serves the same load near **1329 tok/s** on
the *same card*. That ~15× is the GPU finally earning its keep. This bench is the on-demand bench you spin up for exactly
those workloads, then tear down.

---

# Case 2 — SGLang: prefix caching / RadixAttention (use case c)

vLLM and SGLang overlap ~90% on throughput — so SGLang's *reason to exist* in the lab is a different thing: **automatic
prefix caching**. This is the win that maps directly onto how the lab actually uses LLMs — agents with fat system prompts,
RAG with repeated context, multi-turn chat.

## The measured result (the artifact)

`sglang-bench.sh prefix-bench` — 8 requests, a **2.5K-token shared prefix** (a realistic fat system prompt / RAG context),
measuring **TTFT** (time to first token), direct at SGLang:

```
shared-prefix    first= 170.2ms  avg-of-rest=  26.2ms
unique-prefix    first= 176.0ms  avg-of-rest= 163.6ms
```

- **shared-prefix**: request 0 is a cold miss (170ms — full 2.5K-token prefill), then the rest drop to **26.2ms**.
- **unique-prefix**: every request re-prefills the 2.5K tokens → **163.6ms** throughout.

**~6.2× faster TTFT on cache hits** (163.6 → 26.2ms). The tell it's real: the shared run's *first* request (170ms, a
genuine miss) matches the unique baseline (~164ms) — so the speedup is **purely reuse**, not a warm-up artifact.

## Why this happens — RadixAttention

- Recall from Case 1: **prefill** processes the whole prompt at once and builds its **KV cache**. For a 2.5K-token system
  prompt that's real work — and normally it's redone on **every** request that carries that prompt.
- **RadixAttention** stores the KV cache of processed prefixes in a **radix tree** (keyed by token prefix). When a new
  request arrives, SGLang walks the tree and finds the **longest cached prefix match** — for a repeated system prompt,
  that's the *entire* prompt. It **reuses that KV directly** and only prefills the new suffix (the actual question).
- So a cache hit **skips re-prefilling the shared prefix entirely** — TTFT collapses to just the cost of the short new
  suffix. The `unique-prefix` run diverges at token 0, so the tree never matches → every request pays the full prefill.

## Why this matters for the lab

This is *exactly* the lab's LLM shape: the operator and RAG agents send a **large, mostly-constant system prompt +
retrieved context** on every turn, changing only the user's question. RadixAttention means that fat prefix is computed
**once** and reused — cutting TTFT ~6× on the repeated part. That's SGLang's distinct, non-redundant job here; vLLM owns
throughput, SGLang owns prefix reuse.

*(RadixAttention is **on by default** in SGLang — no flag. `--disable-radix-cache` turns it off, which is how you'd
reproduce the `unique-prefix`-like baseline for the whole server.)*

---

# Reproduce it — CLI

## CLI walkthrough (reproduce it)

All on **rogueone**, via the wrapper scripts. (They set `DOCKER_HOST` to the **native Docker engine** — harmless but
redundant since B127 retired Docker Desktop and native became the default context; see the runbook's gotcha 1.)
**Run one bench at a time** on the 16GB card.

**Case 1 — vLLM throughput:**
```
scripts/vllm-bench.sh start          # on-demand; ~5.5GB model download on first run
scripts/vllm-bench.sh status         # → Qwen/Qwen2.5-7B-Instruct-AWQ
python3 nodes/rogueone/services/gpu-inference/bench.py    # the ~15× continuous-batching table
scripts/vllm-bench.sh stop           # free the VRAM
```

**Case 2 — SGLang prefix caching:**
```
scripts/sglang-bench.sh start        # on-demand
scripts/sglang-bench.sh status       # → unsloth/Llama-3.2-1B-Instruct
scripts/sglang-bench.sh prefix-bench # the ~6.2× TTFT shared-vs-unique table
scripts/sglang-bench.sh stop         # free the VRAM
```

Through the gateway (from **mother**) — proves it's a first-class Bifrost provider, tool-free (see runbook for why):
```
kubectl -n weyland exec deploy/weyland-guard -- python -c 'import httpx; r=httpx.post("http://bifrost.weyland.svc.cluster.local:8080/v1/chat/completions",json={"model":"vllm/Qwen/Qwen2.5-7B-Instruct-AWQ","messages":[{"role":"user","content":"say hi in 3 words"}]},headers={"x-bf-mcp-include-tools":""},timeout=90); print(r.status_code); print(r.text[:300])'
# → 200 {"...":"Hello, friend."}
```

## UI walkthrough

Bifrost UI → **Observability → LLM Logs**: the gateway smoke above appears as a `vllm` request (model, tokens, latency).
That's the same lane as every other provider — vLLM is just another governed endpoint, it happens to run on your GPU.

## Teardown

`docker compose ... down` (step 5) removes the container and frees VRAM. The model stays cached in the `hf-cache` volume,
so the next `up` is fast (no re-download). This is a **bench, not a service** — it is *meant* to be down between
experiments, which is why there is deliberately **no Uptime-Kuma monitor** for it.
