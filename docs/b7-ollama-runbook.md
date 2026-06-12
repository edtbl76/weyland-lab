# Ollama Runbook — weyland (CT 102)

Operational runbook for the committed CPU model-serving path (B7 Option B): create/access the
container, install Ollama, pull + tune models, and the critical thread-count fix. Day-to-day ops.

**Related:** [B7 — Model Serving Hardware (the decision)](b7-model-serving-hardware.md) ·
[LLM inference CPU vs GPU (the concepts)](b7-llm-inference-cpu-vs-gpu.md).

---

**Live since 2026-06-11.** Unprivileged LXC `ollama` (CTID **102**) on the weyland Proxmox host.
- **Address:** `192.168.1.244` → API at **`http://192.168.1.244:11434`** (OpenAI-compatible `/v1`).
- **Spec:** 48 GB RAM cap · 14-core *ceiling* (time-shared, not reserved — uses cores only while
  inferring) · 150 GB rootfs on `local-zfs` (NVMe) · `nesting=1` (Debian 12 / systemd 252).

## Access — get a shell in the container
The container has **no direct login** from your workstation; you reach it **through the weyland
Proxmox host**:
1. **SSH to the host:** `ssh emangini@weyland`
2. **Enter the container** (`pct` is root-only — prefix `sudo` if you're not already root):
   - Interactive shell: `pct enter 102`  → lands you at `root@ollama:~#`
   - One-off command without a shell: `pct exec 102 -- ollama list`
3. **Leave** the container shell with `exit` (drops you back on the host).

> Convention for the rest of this runbook: every `ollama …` / `printf …` command runs **inside the
> container** (after `pct enter 102`). Anything that must run on the hypervisor is marked
> **"(on weyland host)"**.

## Create the container (on weyland host)
```bash
pveam update
pveam download local debian-12-standard_12.12-1_amd64.tar.zst
pct create 102 local:vztmpl/debian-12-standard_12.12-1_amd64.tar.zst \
  --hostname ollama --unprivileged 1 --rootfs local-zfs:150
pct set 102 --net0 name=eth0,bridge=vmbr0,ip=dhcp
pct set 102 --cores 14 --memory 49152 --swap 0 --onboot 1 --features nesting=1
pct start 102
pct exec 102 -- hostname -I        # note the DHCP IP (192.168.1.244)
```

## Install Ollama (inside the container: `pct enter 102`)
```bash
apt update && apt install -y curl zstd     # zstd is required by the installer
curl -fsSL https://ollama.com/install.sh | sh
# bind to the LAN (default is 127.0.0.1 only) via a systemd drop-in:
mkdir -p /etc/systemd/system/ollama.service.d
printf '[Service]\nEnvironment="OLLAMA_HOST=0.0.0.0:11434"\n' \
  > /etc/systemd/system/ollama.service.d/override.conf
systemctl daemon-reload && systemctl restart ollama
```

## Where models are stored
- **`/usr/share/ollama/.ollama/models`** — the systemd service runs as the **`ollama` user**, so
  models land in its home (NOT `/root/.ollama`). `blobs/` = weights (content-addressed, dedupes
  shared layers); `manifests/` = which blobs make up each `model:tag`.
- This is on the **150 GB `local-zfs` rootfs → rpool NVMe** — the *right* home (fast load; do NOT
  move to the slow USB/MinIO drive).
- **Out of room?** `pct resize 102 rootfs +100G` (rpool has ~1.5 TB free), or set
  `OLLAMA_MODELS=/path` to a separate dataset.
- **Orphaned blobs from a cancelled pull:** a killed `ollama pull` leaves `…-partial*` files that
  `ollama list` can't see (it reads manifests, not disk) but `du` counts. Find with
  `ls -lhS …/models/blobs` and remove by exact hash:
  `rm -f …/models/blobs/sha256-<hash>-partial*`.

## Run / use
```bash
ollama pull qwen3:30b-a3b          # MoE: ~30B quality at ~3B speed — ideal for CPU
ollama run qwen3:30b-a3b --verbose "..."   # --verbose prints eval rate (tok/s)
ollama list                        # installed models + sizes
```
- **⚠️ After every `ollama pull`, bake in `num_thread 8`** (see *Performance tuning* below) — a
  freshly pulled model defaults to 16 threads and crawls (~160× slower) until you do.
- **Harness / tool-server integration:** point any OpenAI-compatible client at
  `http://192.168.1.244:11434/v1` — same API shape as rogueone's vLLM, so client code is
  engine-agnostic. (Future eGPU → swap Ollama for vLLM, same endpoint.)
- **Service ops (inside CT):** `systemctl status|restart ollama`. Enter the CT from the host with
  `pct enter 102`.

## Performance tuning — CPU thread count (CRITICAL — ~160× fix)

**Symptom (2026-06-11):** `qwen3:30b-a3b` generated at **~0.15 tok/s** (6–7 s *per token*) while
`top` showed **1400 % CPU** (all cores pegged). Compute-bound *and* slow — a contradiction that
pointed straight at the threading model, not the hardware.

**Root cause — thread oversubscription + spin-wait barriers.** The LXC exposes the *host's*
topology (`/proc/cpuinfo` inside CT 102 shows the full **16-core / 32-thread** 9955HX), so
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
core, comfortably inside the 14-CPU cpuset with headroom so no straggler stalls a barrier.

**Measured (`ollama run --verbose`, 30B-A3B Q4, 2026-06-11):**

| Threads | eval rate | vs baseline |
|---|---|---|
| 16 (default) | ~0.15 tok/s | 1× |
| **8 (fixed)** | **24.79 tok/s** | **~160×** |

(prompt eval ~107 tok/s.) **24.79 tok/s on pure CPU for a 30B-A3B MoE is genuinely good** — faster
than reading speed, usable interactively — and it validates the whole Option B thesis: the
slowness was a config trap, not the box's ceiling.

**Why 8, not 14/16:** past one-thread-per-physical-core, extra threads only add barrier + SMT
contention; memory bandwidth saturates first anyway. 8 is proven; 6/10/12 untested — tune later
if a workload wants it.

**Make it permanent (Modelfile — the `/set parameter` in `ollama run` is session-only):**
```bash
printf 'FROM qwen3:30b-a3b\nPARAMETER num_thread 8\n' > /root/Modelfile.qwen3-cpu
ollama create qwen3:30b-a3b -f /root/Modelfile.qwen3-cpu   # re-tags same name, reuses blobs (no re-download)
ollama show qwen3:30b-a3b --parameters                     # verify: num_thread 8
```
**Every model you pull needs the same treatment** — `num_thread` is a *per-model* parameter and
there is no reliable global Ollama thread env, so apply this Modelfile pattern to each new model.
Generic recipe for any `<model:tag>` (run inside the container):
```bash
ollama pull <model:tag>
printf 'FROM <model:tag>\nPARAMETER num_thread 8\n' > /root/Mf
ollama create <model:tag> -f /root/Mf   # re-tags same name + the thread param; reuses blobs
```

## Model architecture note (matters on CPU)
Prefer **MoE models** (e.g. `qwen3:30b-a3b`) on CPU: token-gen reads only the *active* experts
(~3B) per token, so a 30B-total MoE runs at ~3B *speed* with ~30B *capability* — sidestepping the
"dense large models are slow on CPU" problem. Dense `qwen3:14b`/`32b` exist for comparison. The
[measured benchmarks](#measured-benchmarks) below confirm the 1/N active-params law cold.

## Measured benchmarks
Ground-truth `eval rate` from `ollama run --verbose` (supersedes the estimated performance-envelope
tables in [b7-llm-inference-cpu-vs-gpu.md](b7-llm-inference-cpu-vs-gpu.md#performance-envelope--expected-toks-ballpark-q4)).
**Note:** all require the `num_thread 8` fix above; the default-16-thread numbers are meaningless
(spin-wait collapse).

All `num_thread 8`, sorted fastest→slowest (2026-06-11):

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

- [ ] Benchmark a 70B@Q4 (batch/async tier) once pulled — see Tentative roadmap item in backlog.md.
