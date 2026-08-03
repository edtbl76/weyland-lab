# Runbook — On-Demand GPU Inference (vLLM + SGLang) on rogueone

On-demand GPU inference bench on rogueone (RTX 5000 Ada, 16GB), fronted by Bifrost. **Not always-on** — spun up per
experiment, torn down after. Files: `nodes/rogueone/services/gpu-inference/` (`docker-compose.yml`, `bench.py`).
Design: [aidlc-docs/gpu-inference-vllm-sglang-design.md](../../aidlc-docs/gpu-inference-vllm-sglang-design.md).
Demo (continuous batching, extreme detail): [demos/gpu-inference.md](../demos/gpu-inference.md).

## ⚠️ THE TWO GOTCHAS THAT COST A MONTH — read first

### 1. GPU containers MUST run on the NATIVE Docker engine, not Docker Desktop
rogueone's **default** docker context is **Docker Desktop** (`desktop-linux`), which runs in a VM with **no host GPU**.
GPU access lives on the **native Docker Engine** socket (`/var/run/docker.sock`), which has the nvidia runtime configured
(`/etc/docker/daemon.json`). Symptom if you forget: `Error response from daemon: could not select device driver "nvidia"
with capabilities: [[gpu]]`.

Fix = force the native socket per-command (this is exactly what the existing `~/weyland/vllm/gpu-docker` wrapper does —
`env DOCKER_HOST=unix:///var/run/docker.sock docker "$@"`). For compose, prefix every call:
```
DOCKER_HOST=unix:///var/run/docker.sock docker compose -f nodes/rogueone/services/gpu-inference/docker-compose.yml <cmd>
```
Verify the GPU is reachable at all: `docker run --rm --gpus all ubuntu:22.04 nvidia-smi` **on the native engine**.

### 2. vLLM `--gpu-memory-utilization` must cover weights + CUDA graphs + KV cache
The util fraction is the WHOLE budget for the vLLM process, not just weights. Set it too low and vLLM aborts at startup:
`Available KV cache memory: -0.22 GiB` → `RuntimeError: Engine core initialization failed`. For the 7B AWQ:
- `0.25` (~4GB) → **FAILS** — weights (2.98GB) + CUDA graphs (0.49GB) alone ate the budget, leaving negative KV cache.
- `0.55` (~8.8GB) → works — weights ~5.5 (AWQ 4-bit) + graphs/overhead ~1 + KV ~2.3.
With the ~5.5GB baseline (desktop — **no iGPU on rogueone** — + rag-embed), 0.55 puts the card at ~14/16 → **keep Ollama
idle/unloaded during a vLLM bench**, or drop to a smaller model. Freeze risk if you overcommit: [[rogueone-gpu-freeze-vram]].

## Operate — vLLM (P1, use case b: throughput)

**Convenience wrapper** (recommended — sets the native `DOCKER_HOST` + compose path for you), run on rogueone:
`scripts/vllm-bench.sh {start|stop|status|logs|smoke}`. Replaces the old `~/weyland/vllm/start-vllm-qwen`. The raw
compose commands below are what it wraps:

```
# up (first run downloads the model ~5.5GB into the hf-cache volume)
DOCKER_HOST=unix:///var/run/docker.sock docker compose -f nodes/rogueone/services/gpu-inference/docker-compose.yml up -d vllm
# ready?
DOCKER_HOST=unix:///var/run/docker.sock docker compose -f nodes/rogueone/services/gpu-inference/docker-compose.yml logs -f vllm 2>&1 | grep -m1 "Application startup complete"
# serving?
curl -s http://localhost:8001/v1/models | jq -r '.data[].id'
# throughput bench (see demo for the continuous-batching explanation)
python3 nodes/rogueone/services/gpu-inference/bench.py
# down — frees VRAM; model stays cached for next time
DOCKER_HOST=unix:///var/run/docker.sock docker compose -f nodes/rogueone/services/gpu-inference/docker-compose.yml down
```
Change model: edit the `--model` + `--gpu-memory-utilization` in the compose, `up -d --force-recreate vllm`. On a 16GB
card the sweet spot is a **7B AWQ** (`Qwen/Qwen2.5-7B-Instruct-AWQ`, ~5.5GB); `Qwen2.5-3B-Instruct` (bf16) is the safe
middle ground if you need Ollama live alongside; 1.5B is validation-grade only.

Debug a failed start (the real cause is buried — the outer traceback just says "Engine core init failed"):
```
DOCKER_HOST=unix:///var/run/docker.sock docker compose -f nodes/rogueone/services/gpu-inference/docker-compose.yml logs vllm 2>&1 | grep -iE "error|cuda|memory|kv cache|capability|RuntimeError"
```

## Wire into Bifrost

Native `vllm` provider — Base URL `http://192.168.1.230:8001` (**no `/v1`** — Bifrost appends it, same as Ollama), API
key any dummy value, **allow-private-network ON** (Bifrost blocks LAN IPs by default; already enabled from Ollama).
Model string through Bifrost: `vllm/Qwen/Qwen2.5-7B-Instruct-AWQ`. Smoke it tool-free (see the load-out note on why
`x-bf-mcp-include-tools:""` — Bifrost auto-injects the 91 fleet tools into chat otherwise):
```
kubectl -n weyland exec deploy/weyland-guard -- python -c 'import httpx; r=httpx.post("http://bifrost.weyland.svc.cluster.local:8080/v1/chat/completions",json={"model":"vllm/Qwen/Qwen2.5-7B-Instruct-AWQ","messages":[{"role":"user","content":"hi"}]},headers={"x-bf-mcp-include-tools":""},timeout=90); print(r.status_code)'
```
On-demand consequence: when the bench is **down** (or rogueone sleeps), the Bifrost `vllm` provider shows **unhappy** —
expected, not a fault.

## SGLang (use case c: PREFIX CACHING) — LIVE

SGLang's job in the lab = **RadixAttention prefix caching** for agent/RAG (fat repeated system prompts / RAG context).
On-demand via `scripts/sglang-bench.sh {start|stop|status|logs|smoke|prefix-bench}` — same native-engine + VRAM pattern,
`sglang` service in the compose, `:8002`, Bifrost `sgl` provider. Model `unsloth/Llama-3.2-1B-Instruct` (ungated mirror).

```
scripts/sglang-bench.sh start                 # native GPU engine
scripts/sglang-bench.sh status                # → unsloth/Llama-3.2-1B-Instruct
scripts/sglang-bench.sh prefix-bench          # the prefix-cache demo (shared vs unique prefix, TTFT)
scripts/sglang-bench.sh stop
```
**Wire into Bifrost:** native `sgl` provider, Base URL `http://192.168.1.230:8002` (no `/v1`), **dummy key REQUIRED**
(Bifrost 400 "no keys found for provider: sgl" without one — even though SGLang has no auth), allow-private-network ON.
Model string `sgl/unsloth/Llama-3.2-1B-Instruct`.

**SGLang gotchas (differ from vLLM):**
- `--mem-fraction-static` goes **HIGHER** not lower to fix "no KV cache" (`0.55`→negative KV, `0.85` works) — OPPOSITE of
  vLLM's `--gpu-memory-utilization`. It's ~fraction of *available* mem for weights+KV, and weights alone eat ~0.64.
- Gated models 403 even with a token (needs granted access) → use ungated mirrors (`unsloth/…`).
- **RadixAttention (prefix caching) is ON by default** — no flag. `--disable-radix-cache` turns it off.

**REJECTED — prefill/decode (PD) disaggregation.** SGLang PD needs **≥2 GPUs** (prefill GPU 0 / decode GPU 1 via
`--base-gpu-id 1`); rogueone has one. CPU-decode escape is dead too: SGLang's CPU backend is **AMX-only** (Intel Xeon
4th-gen+), rogueone's **i9-13950HX (Raptor Lake) has no AMX**, and SGLang's shipped CPU+GPU disagg is VLM *encode*-on-CPU,
not decode. Real PD = a future 2-GPU play; the prefill/decode *lesson* lives in the demo without running it.

## Llama Guard 8B — guardrails Classify tier-2 (B115) — on-demand
The stronger tier of the guardrails **Classify** layer (see [guardrails.md](guardrails.md)): Meta's **Llama-Guard-3-8B**
content-safety classifier on the GPU, above the always-on 1B (CPU/mother). Uses **llama.cpp** (not vLLM/SGLang — the 1B
tier already uses it, and the GGUF embeds Meta's safety taxonomy). OpenAI-compat on **:8003**. Wrapper:
`scripts/llama-guard-8b.sh {start|stop|status|logs|smoke}` — run on rogueone.

```
scripts/llama-guard-8b.sh start     # first start pulls the ~5.7GB Q5_K_M GGUF into the llama-cache volume
scripts/llama-guard-8b.sh status    # /health
scripts/llama-guard-8b.sh smoke     # classify a benign + a harmful prompt → safe / unsafe\nS<cat>
scripts/llama-guard-8b.sh stop      # free VRAM (GGUF stays cached)
```
- **temp 0** (Llama Guard is random above it); `-ngl 99` offloads all layers. Q5_K_M ~5.7GB — with Ollama on rogueone +
  the desktop sharing the 16GB card, keep Ollama idle if VRAM is tight ([[rogueone-gpu-freeze-vram]]) or drop to Q4_K_M.
- **NOT wired into Bifrost** (unlike the vLLM/SGLang benches) — it's a classifier the guard calls DIRECTLY, not an LLM lane.
- **Re-classify against it:** `LLAMA_GUARD_URL=http://localhost:8003 python3 nodes/mother/lab/weyland-platform/scripts/validate_llama_guard.py`
  (the same 5-case sweep as tier 1). To route the LIVE weyland-guard through it *while it's up*, repoint `LLAMA_GUARD_URL`
  on the guard deployment to `http://192.168.1.230:8003` — but it's on-demand, so normally the guard stays on the
  always-on 1B and the 8B is a manual stronger pass.

## Measured baseline (2026-07-31, Qwen2.5-7B-Instruct-AWQ, 128-tok gens)

Continuous batching — tok/s scales ~linearly with concurrency, latency ~flat (full explanation in the demo):
| concurrency | tok/s | avg latency |
|---|---|---|
| 1 | 88.9 | 1.44s |
| 4 | 363.0 | 1.40s |
| 8 | 742.3 | 1.37s |
| 16 | 1329.5 | 1.52s |

~15× throughput at conc 16 for ~flat latency (93% of ideal linear scaling) — the GPU's tensor cores, idle and
memory-bandwidth-starved at conc 1, get packed by continuous batching amortizing the per-step weight-read across the batch.

**SGLang prefix cache (2026-07-31, Llama-3.2-1B, 2.5K-token shared prefix, TTFT):** `prefix-bench` —
| run | first (cold) | avg-of-rest |
|---|---|---|
| shared-prefix | 170ms (miss) | **26.2ms** (RadixAttention hits) |
| unique-prefix | 176ms | 163.6ms (all misses) |

**~6.2× faster TTFT on cache hits** — a repeated fat prefix is prefilled once and reused. The shared run's *first* request
(≈ the unique baseline) confirms the speedup is pure prefix reuse. This is the lab's agent/RAG pattern (constant system
prompt + retrieved context per turn), and SGLang's distinct job vs vLLM's throughput.

## DoD note
On-demand bench → **no Kuma monitor** (it's meant to be down). DoD here = this runbook + the demo + the recorded numbers +
GitOps-reproducible compose. See [definition-of-done.md](../definition-of-done.md).
