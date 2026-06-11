# B7 — Model Serving Hardware (DECISION DEFERRED — pending pricing)

**Status:** 🟡 OPEN. The *architecture* is settled; the *GPU purchase* is **deferred** until
pricing is researched. This doc captures every option + exact hardware so the decision can be
made cold later without re-deriving anything.

---

## Decision status — what's settled vs open
- **Settled / proceeding NOW:** weyland (MS-A2) is the **dedicated large-model host** via
  **Ollama on CPU** — we move forward with this **regardless of any GPU decision**, so there is
  a **guaranteed CPU path either way**. rogueone stays the GPU/vLLM host for small fast models.
- **Tentative / someday (GPU, low priority — NOT pursued now):** an **OCuLink eGPU** would
  accelerate (~10× on ≤32B), but the lab doesn't need the speed yet, so it's parked at the end of
  the roadmap as *tentative*. Will invest eventually if a real workload feels too slow. **The eGPU
  augments — never replaces — the CPU/Ollama path.** (Options + unverified pricing kept below.)

---

## Current architecture (settled)
| Host | Hardware | Role |
|---|---|---|
| **rogueone** (Lenovo ThinkPad P16 Gen 2) | i9-13950HX · 128 GB RAM · **RTX 5000 Ada Laptop, 16 GB** | GPU / **vLLM**, small fast models; personal + dev laptop |
| **weyland** (Minisforum MS-A2) | Ryzen 9 9955HX (16C) · 96 GB RAM · **no compute GPU** (Radeon display iGPU only) | Proxmox host: `vm-100` openclaw, `vm-101` mother (k3s platform + MinIO). **Intended large-model host.** |

## The problem
Large models need **VRAM or patience**. 30B@4-bit ≈ 20 GB, 70B@4-bit ≈ 40 GB, 70B fp16 ≈ 140 GB.
rogueone's 16 GB GPU is too small; weyland has 96 GB RAM but **no GPU** (CPU inference works but
is slow). B7 = decide how weyland serves big models.

## Background — the inference tradeoff (the *why*, generalizable)

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

weyland CPU ceiling ≈ **~70–80 GB/s** DDR5 (dual-channel ~5600). Reading speed anchor ≈ 7–10 tok/s.
Numbers are estimates — **benchmark with `ollama run` once it's up** (a useful first lab result).

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

---

## MS-A2 expansion capability (how a GPU attaches)
- **Internal PCIe slot:** x16 physical @ **x8 Gen4** (splittable to 2× x4). **BUT** physically
  only fits **single-slot, low-profile** cards (≤ ~16–20 GB class) — too small for big models.
- **OCuLink (the real path):** optional **Minisforum OCuLink adapter** takes 4 lanes from the
  slot to a rear port → an **external eGPU dock** → holds a full-size desktop GPU.
- **Kit needed:** OCuLink adapter **+** eGPU dock (**Minisforum DEG1** or **DEG2**, or generic
  OCuLink dock) **+** an **ATX PSU** sized to the card.
- **Link = PCIe 4.0 x4** (~8 GB/s): fine for inference (weights resident in VRAM; only a small
  model-*load*-time penalty, not tokens/sec). Matters for training, not single-GPU inference.
- **Proxmox:** VFIO-passthrough the eGPU to a model-serving VM. OCuLink is a *fixed* PCIe link
  (not Thunderbolt hot-plug), so it presents as a stable PCIe device → reliable passthrough.

---

# OPTION A — OCuLink eGPU on weyland  *(DEFERRED upgrade — additive to Ollama)*

Kit: OCuLink adapter + DEG1/DEG2 dock + ATX PSU + one GPU below. Serve via **vLLM** (VFIO
passthrough). **Baseline for comparison = rogueone's laptop RTX 5000 Ada: 16 GB / ~576 GB/s.**

### Candidate GPUs — exact models (pick by VRAM target + budget)
> ⚠️ **PRICES BELOW ARE UNVERIFIED ESTIMATES AND PROVED UNRELIABLE** — the user spot-checked
> them 2026-06-11 and found them off by ~10×. They are AI-recalled guesses, not sourced data.
> **Treat every $ figure as a placeholder; get real current listings before any purchase.** The
> only safe takeaway is the *relative* ordering (3090 < 4090 < A6000). TODO: replace with sourced
> prices (region + marketplace).
> "BW" = memory bandwidth (sets token-gen speed). Cooling matters in an enclosed dock:
> **blower/workstation** cards exhaust out the back (dock-friendly); **open-air gaming** cards
> dump heat inside the dock.

#### 16 GB tier — ⚠️ NOT recommended (no VRAM gain over your laptop)
| Exact model | VRAM | BW | CUDA | Arch | TDP | Cooling | ~Price | Notes |
|---|---|---|---|---|---|---|---|---|
| ⬅ **RTX 5000 Ada Laptop — YOURS (rogueone)** | 16 GB | 576 GB/s | 9728 | Ada (FP8) | 80–175 W | (in laptop) | — | **reference point.** Decent speed (~576 GB/s), but 16 GB is the model-size *floor* — every 24/32/48 GB tier below outranks it for what it can run |
| RTX 4060 Ti 16GB | 16 GB | 288 GB/s | 4352 | Ada | 165 W | open-air | ~$450 | slower BW than your laptop; skip |
| RTX 4070 Ti SUPER 16GB | 16 GB | 672 GB/s | 8448 | Ada | 285 W | open-air | ~$800 | only buy as a cheap *dedicated* card, not for size |
| RTX 5060 Ti 16GB | 16 GB | 448 GB/s | 4608 | Blackwell | 180 W | open-air | ~$430 | FP4/FP8, but still 16 GB |

#### 24 GB tier — 30B-class fully on GPU (the practical "large model")
| Exact model | VRAM | BW | CUDA | Arch | TDP | Cooling | ~Price | Notes |
|---|---|---|---|---|---|---|---|---|
| **RTX 3090** ⭐ value | 24 GB | 936 GB/s | 10496 | Ampere | 350 W | open-air (3-slot) | **~$700–900 used** | best $/capability; ~1.6× your laptop's token speed |
| RTX 3090 Ti | 24 GB | 1008 GB/s | 10752 | Ampere | 450 W | open-air | ~$900–1100 used | marginally faster, hotter |
| RTX 4090 | 24 GB | 1008 GB/s | 16384 | Ada (FP8) | 450 W | open-air (3–4 slot) | ~$1500–2000 | fastest 24 GB; big physical card |
| RTX A5000 | 24 GB ECC | 768 GB/s | 8192 | Ampere | 230 W | **blower (2-slot)** | ~$1200–1800 used | dock-friendly: low power + blower |

#### 32 GB tier — bigger context / 30B at higher quant (not full 70B@4-bit)
| Exact model | VRAM | BW | CUDA | Arch | TDP | Cooling | ~Price | Notes |
|---|---|---|---|---|---|---|---|---|
| RTX 5090 | 32 GB | ~1792 GB/s | 21760 | Blackwell | 575 W | open-air | ~$2000–3000+ | fastest here; heavy power draw |
| RTX 5000 Ada (desktop) | 32 GB ECC | 576 GB/s | 12800 | Ada (FP8) | 250 W | **blower (2-slot)** | ~$3500–4000 | desktop sibling of your laptop card; efficient |

#### 48 GB tier — 70B @ 4-bit fully on GPU
| Exact model | VRAM | BW | CUDA | Arch | TDP | Cooling | ~Price | Notes |
|---|---|---|---|---|---|---|---|---|
| **RTX A6000** ⭐ 70B value | 48 GB ECC | 768 GB/s | 10752 | Ampere | 300 W | **blower (2-slot)** | ~$3000–4500 (used ~$2800) | the homelab 70B card; dock-friendly |
| RTX 6000 Ada | 48 GB ECC | 960 GB/s | 18176 | Ada (FP8) | 300 W | **blower (2-slot)** | ~$6000–7000 | premium; fastest 48 GB |
| 2× RTX 3090 (tensor-parallel) | 48 GB | 936 GB/s ea | 10496 ea | Ampere | 350 W ea | open-air | ~$1400–1800 used | cheapest 48 GB, but needs **dual-GPU dock / 2× OCuLink** + TP config — most complex |

### Option A bill of materials (example, 24 GB path)
MS-A2 **OCuLink adapter** + **Minisforum DEG1/DEG2** dock + **~650–750 W ATX PSU** +
**used RTX 3090 (24 GB)** ≈ **~$900–1000 all-in**. (A6000 48 GB path ≈ ~$3,200–4,700 all-in.)

---

# OPTION B — CPU inference on weyland via Ollama  ✅ **COMMITTED (proceeding now, $0)**
**This is the decided baseline — we move forward with it now regardless of the GPU decision, so
there's a guaranteed CPU path.** `ollama` (wraps `llama.cpp`) on the 96 GB RAM. Fits
**70B @ 4-bit (~40 GB)** comfortably.
- Speed (memory-bandwidth-bound on DDR5): **~30B@4-bit a few tok/s, 70B@4-bit ~1–2 tok/s.**
- Fine for non-interactive/batch harness runs; slow for interactive — which is exactly what a
  later eGPU (Option A) accelerates. The eGPU is **additive**: Ollama/CPU stays as a path.
- Serves an OpenAI-compatible `/v1` API, so the tool server / harness points at it **now** and
  needs **no client change** if/when a GPU is added.

# OPTION C — Cloud GPU  *(no capex, opex + data leaves LAN)*
Rent on demand (RunPod / Vast.ai / Lambda) for occasional heavy 70B runs. Against the LAN-lab
ethos for always-on use, and recurring cost — but zero hardware and instantly any size.

---

## Pecking order — where your laptop card sits (frame of reference)
LLM inference ranks on two axes: **VRAM = what you can run** (dominant) and **bandwidth = how
fast**. Your **RTX 5000 Ada Laptop (16 GB / 576 GB/s)** lands:
- **By capacity (VRAM): the floor** — every candidate is 24/32/48 GB, i.e. all run *bigger*
  models than your laptop. This is the axis that matters for B7.
- **By speed (bandwidth): mid-pack** — see the order below.
- **Fun reference:** the **desktop RTX 5000 Ada (32 GB)** is literally your laptop card's desktop
  sibling — same ~576 GB/s, but **2× the VRAM** and more cores.

Ordered by **memory bandwidth** (≈ token-gen speed), your card marked ⬅:

| Rank | GPU | VRAM | BW | ≈ speed vs yours | ~Price |
|---|---|---|---|---|---|
| 1 | RTX 5090 | 32 GB | ~1792 GB/s | ~3.1× | ~$2000–3000 |
| 2 | RTX 4090 | 24 GB | 1008 GB/s | ~1.75× | ~$1500–2000 |
| 2 | RTX 3090 Ti | 24 GB | 1008 GB/s | ~1.75× | ~$900–1100 |
| 4 | RTX 6000 Ada | 48 GB | 960 GB/s | ~1.7× | ~$6000–7000 |
| 5 | RTX 3090 | 24 GB | 936 GB/s | ~1.6× | ~$700–900 |
| 6 | RTX A6000 | 48 GB | 768 GB/s | ~1.3× | ~$3000–4500 |
| 6 | RTX A5000 | 24 GB | 768 GB/s | ~1.3× | ~$1200–1800 |
| 8 | RTX 4070 Ti SUPER | 16 GB | 672 GB/s | ~1.2× | ~$800 |
| **9** | ⬅ **RTX 5000 Ada Laptop — YOURS** | **16 GB** | **576 GB/s** | **1.0× (baseline)** | — |
| 9 | RTX 5000 Ada (desktop) | 32 GB | 576 GB/s | 1.0× | ~$3500–4000 |
| 11 | RTX 5060 Ti 16GB | 16 GB | 448 GB/s | ~0.8× | ~$430 |
| 12 | RTX 4060 Ti 16GB | 16 GB | 288 GB/s | ~0.5× | ~$450 |

**Takeaway:** your laptop card is upper-bottom on *speed* and at the *floor* on *capacity*. The
limit for B7 is VRAM (16 GB), not speed — so every 24 GB+ card is an upgrade for the real goal
(running 30B/70B), and most are faster too. The 3090 (rank 5) is the value pick: ~1.6× your
speed and 24 GB, ~$700–900.

---

## Plan
- **Now (committed):** Option B — **Ollama on weyland's CPU** (96 GB RAM). Guarantees a CPU path
  and gives the harness a working large-model endpoint regardless of GPU timing. Build this.
- **Deferred upgrade (additive, pending pricing):** Option A — OCuLink eGPU. Lean: used
  **RTX 3090 (24 GB)** (~$900–1000) for 30B-class via vLLM; **RTX A6000 (48 GB)** if 70B@4-bit on
  GPU is a hard requirement. The eGPU *accelerates*; it does **not** remove the Ollama path.

## To research before deciding (the deferred bits)
- [ ] Current pricing: MS-A2 OCuLink adapter, **DEG1 vs DEG2** dock, ATX PSU, and the candidate
      cards (used market for 3090 / A6000).
- [ ] Confirm the exact **MS-A2 OCuLink adapter** part (not all Minisforum minis share one).
- [ ] Dock **cooling** for the chosen card (blower workstation vs open-air gaming).
- [ ] Pin the **target model size** (30B vs 70B) → sets the VRAM tier.
- [ ] Power budget / physical space for dock + ATX PSU next to the MS-A2.

---

# Deployment runbook — Ollama on weyland (CT 102)

**Live since 2026-06-11.** Unprivileged LXC `ollama` (CTID **102**) on the weyland Proxmox host.
- **Address:** `192.168.1.244` → API at **`http://192.168.1.244:11434`** (OpenAI-compatible `/v1`).
- **Spec:** 48 GB RAM cap · 14-core *ceiling* (time-shared, not reserved — uses cores only while
  inferring) · 150 GB rootfs on `local-zfs` (NVMe) · `nesting=1` (Debian 12 / systemd 252).

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

## Run / use
```bash
ollama pull qwen3:30b-a3b          # MoE: ~30B quality at ~3B speed — ideal for CPU
ollama run qwen3:30b-a3b --verbose "..."   # --verbose prints eval rate (tok/s)
ollama list                        # installed models + sizes
```
- **Harness / tool-server integration:** point any OpenAI-compatible client at
  `http://192.168.1.244:11434/v1` — same API shape as rogueone's vLLM, so client code is
  engine-agnostic. (Future eGPU → swap Ollama for vLLM, same endpoint.)
- **Service ops (inside CT):** `systemctl status|restart ollama`. Enter the CT from the host with
  `pct enter 102`.

## Model architecture note (matters on CPU)
Prefer **MoE models** (e.g. `qwen3:30b-a3b`) on CPU: token-gen reads only the *active* experts
(~3B) per token, so a 30B-total MoE runs at ~3B *speed* with ~30B *capability* — sidestepping the
"dense large models are slow on CPU" problem. Dense `qwen3:14b`/`32b` exist for comparison.

## TODO — measured benchmarks (replace estimates)
- [ ] Record real `eval rate` (tok/s) per model from `ollama run --verbose` — supersedes the
      estimated Performance-envelope tables above.
