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

## SGLang (P2, use case c: prefill/decode disaggregation) — TODO

Not yet stood up. Will land in the same compose as `sglang`, same native-engine + VRAM-cap pattern, running SGLang's
**PD-disaggregation** mode (separate prefill + decode servers + mini load-balancer) → Bifrost `sgl` provider on `:8002`.
On a single GPU this is a **learning artifact** (real P/D speedup needs ≥2 GPUs + KV transfer), and the deliverable is the
measured prefill-vs-decode split, not throughput.

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

## DoD note
On-demand bench → **no Kuma monitor** (it's meant to be down). DoD here = this runbook + the demo + the recorded numbers +
GitOps-reproducible compose. See [definition-of-done.md](../definition-of-done.md).
