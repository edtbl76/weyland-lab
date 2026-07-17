# Ollama Runbook — rogueone (GPU)

Operational runbook for the Ollama model-serving path: install/access on rogueone, pull + tune
models, the critical thread-count fix, and smoke tests. Day-to-day ops.

**Related:** [B7 — Model Serving Hardware (the decision)](../concepts/model-serving-hardware.md) ·
[LLM inference CPU vs GPU (the concepts)](../concepts/llm-inference-cpu-vs-gpu.md).

---

**Moved to rogueone 2026-07-12 (B79).** Ollama runs natively on **rogueone** (Lenovo ThinkPad P16,
RTX 5000 Ada 16 GB, 128 GB RAM). It was originally the committed CPU path on the weyland Proxmox
host (unprivileged LXC `ollama`, CTID 102, `192.168.1.244`); **B79 decommissioned CT-102 and re-homed
Ollama to rogueone's GPU**, which freed 32 GB on weyland to grow mother 50 → 64 GB. The thread-tuning
and CPU benchmark sections below were measured on the original CT-102 CPU deployment and are kept as
reference — they still apply to the CPU-offloaded portion of any model that overflows the 16 GB VRAM.

- **Address:** `192.168.1.230` → API at **`http://192.168.1.230:11434`** (OpenAI-compatible `/v1`),
  DNS **`ollama.weyland.lab`**. LAN-bound via `OLLAMA_HOST=0.0.0.0:11434`.
- **Hardware:** RTX 5000 Ada (16 GB VRAM) + 128 GB RAM. Models that fit in VRAM run fully on GPU;
  larger models (e.g. 30B@Q4 ≈ 20 GB) offload the overflow layers to CPU/RAM.
- **Serves:** the eval-judge panel, weyland-tool-server RAG (`/context/ask`), Open WebUI, and Hermes.

## Access — get a shell on rogueone
rogueone is a first-class LAN host with a normal login (no `pct` — that was the CT-102 era):
1. **SSH to rogueone:** `ssh edwardmangini@rogueone`
2. **Service ops:** `systemctl status|restart ollama`; one-off commands run directly, e.g. `ollama list`.

> Convention for the rest of this runbook: every `ollama …` / `printf …` command runs **on rogueone**
> (after `ssh edwardmangini@rogueone`).

## Install Ollama (on rogueone)
```bash
curl -fsSL https://ollama.com/install.sh | sh
# bind to the LAN (default is 127.0.0.1 only) via a systemd drop-in:
sudo mkdir -p /etc/systemd/system/ollama.service.d
printf '[Service]\nEnvironment="OLLAMA_HOST=0.0.0.0:11434"\n' \
  | sudo tee /etc/systemd/system/ollama.service.d/override.conf
sudo systemctl daemon-reload && sudo systemctl restart ollama
```
The installer detects the RTX 5000 Ada and pulls the CUDA runtime automatically — `ollama ps` shows a
`PROCESSOR` column (`GPU` / `CPU` / split) per loaded model.

## Where models are stored
- **`/usr/share/ollama/.ollama/models`** — the systemd service runs as the **`ollama` user**, so
  models land in its home (NOT `/root/.ollama`). `blobs/` = weights (content-addressed, dedupes
  shared layers); `manifests/` = which blobs make up each `model:tag`.
- rogueone has 128 GB RAM and ample local NVMe — keep models on fast local disk (do NOT move to the
  slow USB/MinIO drive). Set `OLLAMA_MODELS=/path` to relocate to a bigger dataset if needed.
- **Orphaned blobs from a cancelled pull:** a killed `ollama pull` leaves `…-partial*` files that
  `ollama list` can't see (it reads manifests, not disk) but `du` counts. Find with
  `ls -lhS …/models/blobs` and remove by exact hash:
  `rm -f …/models/blobs/sha256-<hash>-partial*`.

## Run / use
```bash
ollama pull qwen3:30b-a3b          # MoE: ~30B quality at ~3B speed
ollama run qwen3:30b-a3b --verbose "..."   # --verbose prints eval rate (tok/s)
ollama list                        # installed models + sizes
```
- **⚠️ For CPU-offloaded models, bake in `num_thread 8`** (see *Performance tuning* below) — a freshly
  pulled model defaults to 16 threads and the CPU-offloaded layers crawl until you do.
- **Harness / tool-server integration:** point any OpenAI-compatible client at
  `http://192.168.1.230:11434/v1` — same API shape as rogueone's vLLM, so client code is
  engine-agnostic.
- **Service ops:** `systemctl status|restart ollama`.

## Consumers — who calls this endpoint
- **weyland-tool-server** (mother / k3s, **v0.3.0+**) — its `/context/ask` does RAG against this
  endpoint: retrieve top-k from a vector backend → synthesize a grounded answer via the local
  model. Configured by `OLLAMA_BASE_URL=http://192.168.1.230:11434/v1` and
  `OLLAMA_MODEL=gpt-oss:20b` (default since B4 panel; callers override per request via the `model` field).
  `GET /models` lists the choices; `GET /ollama/health` and `/status`→`.llm` report reachability.
  Deploy/test recipes:
  [test-commands.md](../validation/test-commands.md) → *Tool Server → LLM / RAG*.

**The `/context/ask` RAG pipeline** — note the **two distinct models** (embedding vs generation):

```text
your question
   │
   ├─▶ 1. EMBED the question        ← BAAI/bge-small-en-v1.5 (baked into the tool-server)
   │
   ├─▶ 2. RETRIEVE top-k chunks     ← one of pgvector / qdrant / weaviate / neo4j
   │
   ├─▶ 3. GENERATE grounded answer  ← one of the 6 Ollama models (this endpoint)
   │
   └─▶ {answer, model, sources}
```

- **Generation (step 3)** is any of the 6 Ollama models, selectable per request (the `model`
  field; default `qwen3:30b-a3b`). Switching models changes *how the answer is written*, not
  *what's retrieved*.
- **Embedding (step 1)** is a separate, **fixed** model (`bge-small`, in the tool-server image) —
  it's what finds the relevant chunks, is **not** one of the 6, and doesn't change when you pick a
  different generation model. So all 6 reason over the *same* retrieved context.

## Performance tuning — CPU thread count (CRITICAL for CPU-offloaded layers — ~160× fix)

> Measured on the original **CT-102 CPU deployment** (2026-06-11), kept as reference. Still applies to
> the CPU-offloaded portion of any model too large for the 16 GB VRAM on rogueone.

**Symptom (2026-06-11):** `qwen3:30b-a3b` generated at **~0.15 tok/s** (6–7 s *per token*) while
`top` showed **1400 % CPU** (all cores pegged). Compute-bound *and* slow — a contradiction that
pointed straight at the threading model, not the hardware.

**Root cause — thread oversubscription + spin-wait barriers.** The LXC exposed the *host's*
topology (`/proc/cpuinfo` inside CT 102 showed the full **16-core / 32-thread** 9955HX), so
llama.cpp auto-set **`n_threads = 16`** off the host physical-core count — ignoring the
container's 14-CPU cpuset (the `system_info` line read `n_threads = 16 ... / 14`). llama.cpp
synchronizes **every model layer with busy-wait barriers**: a worker that reaches the barrier
early **spins at 100 % CPU** until the others arrive (low-latency by design, assuming one thread
per dedicated physical core). With 16 threads contending for ~14 (really ~7–8 truly-free) cores,
the OS constantly deschedules threads, so at each barrier the running threads **spin uselessly
waiting on a descheduled sibling**. Net effect: **all cores pegged (spinning), almost no matmul
progress** — the 1400 %-CPU-yet-0.15-tok/s paradox. SMT compounds it: two hyperthreads share one
AVX-512 vector unit, so packing siblings adds contention, not parallelism. (Confirmed *not*
governor — `performance`, cores boosting to 5 GHz — and *not* missing kernels — `AVX512_VNNI`,
`AVX512_BF16`, `REPACK`, `LLAMAFILE` all `= 1`.)

**Fix — pin `num_thread` to ≤ physical cores.** Set **`num_thread = 8`**: one thread per physical
core with headroom so no straggler stalls a barrier.

**Measured (`ollama run --verbose`, 30B-A3B Q4, 2026-06-11, CT-102 CPU):**

| Threads | eval rate | vs baseline |
|---|---|---|
| 16 (default) | ~0.15 tok/s | 1× |
| **8 (fixed)** | **24.79 tok/s** | **~160×** |

(prompt eval ~107 tok/s.) **24.79 tok/s on pure CPU for a 30B-A3B MoE is genuinely good** — faster
than reading speed, usable interactively — and it validated the whole Option B thesis: the
slowness was a config trap, not the box's ceiling.

**Why 8, not 14/16:** past one-thread-per-physical-core, extra threads only add barrier + SMT
contention; memory bandwidth saturates first anyway. 8 is proven; 6/10/12 untested — tune later
if a workload wants it.

**Make it permanent (Modelfile — the `/set parameter` in `ollama run` is session-only):**
```bash
printf 'FROM qwen3:30b-a3b\nPARAMETER num_thread 8\n' > ~/Modelfile.qwen3-cpu
ollama create qwen3:30b-a3b -f ~/Modelfile.qwen3-cpu   # re-tags same name, reuses blobs (no re-download)
ollama show qwen3:30b-a3b --parameters                 # verify: num_thread 8
```
**Every CPU-offloaded model you pull needs the same treatment** — `num_thread` is a *per-model*
parameter and there is no reliable global Ollama thread env, so apply this Modelfile pattern to each
new model. Generic recipe for any `<model:tag>` (run on rogueone):
```bash
ollama pull <model:tag>
printf 'FROM <model:tag>\nPARAMETER num_thread 8\n' > ~/Mf
ollama create <model:tag> -f ~/Mf   # re-tags same name + the thread param; reuses blobs
```

## Memory — keep one model resident

**Symptom (2026-06-13, CT-102):** a multi-model batch (the B4 eval — 6 models in sequence)
**OOM-killed Ollama** after ~2 big models: `ollama.service: A process of this unit has been killed by
the OOM killer … Failed with result 'oom-kill'`. Every `/context/ask` 502'd from then on.

**Root cause — Ollama sized against the *host*, not the container's 48 GB cgroup.** With
**`OLLAMA_MAX_LOADED_MODELS=0`** (auto) it kept *multiple* models resident (2× ~19 GB), blew past the
cap, and the cgroup OOM-killed the process. rogueone's 128 GB gives far more headroom, but pinning one
model resident is still the right default for sequential multi-model workloads.

**Fix — pin one model resident** so it always evicts before loading the next:
```bash
printf '[Service]\nEnvironment="OLLAMA_MAX_LOADED_MODELS=1"\n' | sudo tee -a /etc/systemd/system/ollama.service.d/override.conf
sudo systemctl daemon-reload && sudo systemctl restart ollama
```
Sequential multi-model workloads (evals, A/B comparisons) then just **load → serve → evict** per model.

## Context window + keep-alive (added 2026-06-13 for the B2 agent)

Two more env vars in the same drop-in, driven by the Hermes agent (B2) but affecting **all**
consumers (RAG, Open WebUI, evals):

```bash
printf '[Service]\nEnvironment="OLLAMA_CONTEXT_LENGTH=65536"\nEnvironment="OLLAMA_KEEP_ALIVE=-1"\n' \
  | sudo tee -a /etc/systemd/system/ollama.service.d/override.conf
sudo systemctl daemon-reload && sudo systemctl restart ollama
# verify: all vars present
systemctl show ollama -p Environment
# verify the served window (loaded model): CONTEXT column
ollama ps
```

- **`OLLAMA_CONTEXT_LENGTH`** — Ollama's default served context is a stingy **4096**. That truncated
  agent turns (a tool-heavy prompt + answer overflowed 4K → `finish_reason=length`, 1-token output).
  Raised to **65536**. **Why not the model's native 262K?** KV-cache RAM grows linearly with the
  window (~165 MB per 1K tokens for a 30B model): 32K≈20 GB, 64K≈25 GB, 128K≈36 GB, 262K≈~58 GB. 64K
  leaves ample conversation room. Cost scales with tokens *used*, not the *allocation*, so a large
  window you don't fill is cheap.
- **`OLLAMA_KEEP_ALIVE=-1`** — default keep-alive is ~5 min, so the model **unloads between turns**
  and every prompt after a pause pays a cold reload (and can time out the client). `-1` pins it
  resident. Bounded by `MAX_LOADED_MODELS=1` (still one model), so no extra RAM beyond the single
  resident model.
- **Prompt caching (free win):** llama.cpp caches the prompt-prefix KV, so an unchanged system
  prompt is prefilled **once** — later turns reuse it (we saw turn-2 prefill drop from 13.5K tokens
  to ~111). The cache **survives a Hermes restart** (it lives here, keyed by prefix + resident model)
  but **dies on Ollama restart or model eviction** — so don't churn this service if you want warm
  turns. Any cross-model request (a different model) evicts + cold-loads.

> **Consumer pairing:** a client's declared context length **must match** `OLLAMA_CONTEXT_LENGTH`.
> If a client thinks the window is larger (e.g. Hermes auto-detecting the model's 262K), it packs
> past 64K and Ollama **silently drops the overflow**. Keep both equal.

## Model architecture note (matters when CPU-offloaded)
Prefer **MoE models** (e.g. `qwen3:30b-a3b`): token-gen reads only the *active* experts
(~3B) per token, so a 30B-total MoE runs at ~3B *speed* with ~30B *capability* — sidestepping the
"dense large models are slow on CPU" problem for the layers that spill out of VRAM. Dense
`qwen3:14b`/`32b` exist for comparison. The [measured benchmarks](#measured-benchmarks) below confirm
the 1/N active-params law cold.

## Measured benchmarks
Ground-truth `eval rate` from `ollama run --verbose`, measured on the **original CT-102 CPU
deployment** (supersedes the estimated performance-envelope tables in
[../concepts/llm-inference-cpu-vs-gpu.md](../concepts/llm-inference-cpu-vs-gpu.md#performance-envelope--expected-toks-ballpark-q4)).
**Note:** all require the `num_thread 8` fix above; the default-16-thread numbers are meaningless
(spin-wait collapse). GPU offload on rogueone lifts models that fit VRAM well above these figures.

All `num_thread 8`, sorted fastest→slowest (2026-06-11, CT-102 CPU):

| Model | Type (active params) | eval rate | prompt eval |
|---|---|---|---|
| `deepseek-coder-v2:16b` | MoE 16B / **~2.4B** active | **35.26 tok/s** | 131 tok/s |
| `qwen3-coder:30b` | MoE 30B / **~3B** active | **25.80 tok/s** | 71 tok/s |
| `qwen3:30b-a3b` | MoE 30B / **~3B** active | **24.79 tok/s** | ~107 tok/s |
| `gpt-oss:20b` | MoE ~21B / **~3.6B** active (MXFP4) | **13.66 tok/s** | 99 tok/s |
| `qwen3:14b` | **dense 14B** | **5.24 tok/s** | 49 tok/s |
| `mistral-small3.2:24b` | **dense 24B** | **3.61 tok/s** | 35 tok/s |

**What this shows — speed tracks *active* params at ~1/N (bandwidth-bound), and the MoE trick is
the whole game on CPU:**
- **The 1/N law holds across architectures.** Token-gen reads only the active weights, so
  `eval rate ∝ 1 / active-params`. From the ~3B-active MoE anchor (~25 tok/s) you can *predict* the
  dense models: 14B → 25×3/14 ≈ **5.4** (measured **5.24** ✓); 24B → 25×3/24 ≈ **3.1** (measured
  **3.61** ✓). Dense pays for *every* parameter each token; MoE pays only for the active slice.
- **`deepseek-coder-v2:16b` is the CPU speed king** (35 tok/s) — lowest active count (2.4B) wins.
  The two ~3B-active coder/MoE qwens tie at ~25. These three are the **interactive** tier for
  harness/agent work.
- **`gpt-oss:20b` underperforms its active-param count** — ~3.6B active "should" sit near 20 tok/s
  but lands at 13.66. Likely **MXFP4 dequant is less CPU-optimized than Q4_K** (or heavier
  attention/routing). Still usable, just not as fast as the qwens.
- **Prefill (prompt eval) is healthy (35–131 tok/s),** but note `mistral-small3.2`'s 515-token
  prompt (its large multimodal chat template) cost **~15 s before the first token** — the
  prefill-scales-with-prompt-length tax, in the wild.

- [ ] Re-benchmark the interactive tier on rogueone's GPU offload — see backlog.md.
