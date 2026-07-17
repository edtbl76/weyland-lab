# B7 — Model Serving Hardware (GPU-served on rogueone; weyland eGPU purchase deferred)

**Status:** 🟢 Large-model serving is **live on GPU** — B79 (2026-07-12) moved Ollama off the weyland
CPU LXC (CT-102, now retired) onto **rogueone's existing RTX 5000 Ada** (16 GB). The remaining open
item is the *dedicated weyland eGPU purchase*, which stays **deferred** until pricing is researched.
This doc captures every option + exact hardware so that purchase can be made cold later without
re-deriving anything.

> **This doc was split (2026-06-11) for length.** It now holds only the **decision** (what to buy,
> options, candidate GPUs, plan). The other two pieces live separately:
> - **The *why* — inference concepts** (capacity vs bandwidth, CPU vs GPU routing, tiered
>   inference): [llm-inference-cpu-vs-gpu.md](llm-inference-cpu-vs-gpu.md)
> - **The *how* — operating Ollama** (container, install, thread fix, measured benchmarks):
>   [../runbooks/model-serving-ollama.md](../runbooks/model-serving-ollama.md)

---

## Decision status — what's settled vs open
- **Settled / live NOW:** large-model serving runs **Ollama on rogueone's GPU** (RTX 5000 Ada 16 GB;
  overflow layers offload to its 128 GB RAM). B79 (2026-07-12) moved it off the weyland CPU LXC
  (CT-102, retired), freeing 32 GB to grow mother 50 → 64 GB (see
  [runbook](../runbooks/model-serving-ollama.md)). rogueone also stays the vLLM host for small fast
  models.
- **Tentative / someday (dedicated weyland eGPU, low priority — NOT pursued now):** an **OCuLink
  eGPU** on the MS-A2 would give weyland its own accelerator (and larger VRAM than rogueone's 16 GB),
  but the lab doesn't need it yet, so it's parked at the end of the roadmap as *tentative*. Will
  invest eventually if a real workload feels too slow. (Options + unverified pricing kept below.)

---

## Current architecture (settled)
| Host | Hardware | Role |
|---|---|---|
| **rogueone** (Lenovo ThinkPad P16 Gen 2) | i9-13950HX · 128 GB RAM · **RTX 5000 Ada Laptop, 16 GB** | GPU / **vLLM** (small fast models) **+ Ollama** (B79, `192.168.1.230:11434` / `ollama.weyland.lab` — moved off CT-102; **the large-model host now**, GPU + 128 GB RAM offload); personal + dev laptop |
| **weyland** (Minisforum MS-A2) | Ryzen 9 9955HX (16C) · 96 GB RAM · **no compute GPU** (Radeon display iGPU only) | Proxmox host: `vm-100` openclaw, `vm-101` mother (k3s platform + MinIO). `ct-102` ollama **RETIRED (B79)** — the freed 32 GB grew mother 50 → 64 GB. |

## The problem
Large models need **VRAM or patience**. 30B@4-bit ≈ 20 GB, 70B@4-bit ≈ 40 GB, 70B fp16 ≈ 140 GB.
rogueone's 16 GB GPU is too small; weyland has 96 GB RAM but **no GPU** (CPU inference works but
is slow). B7 = decide how weyland serves big models.

**For the reasoning behind everything below** — why token speed is bandwidth-bound, when CPU vs
GPU each make sense, the tiered-inference pattern, and how the lab context weights it all — see
**[llm-inference-cpu-vs-gpu.md](llm-inference-cpu-vs-gpu.md)**. Short version: **CPU = capacity
(big, cheap, slow); GPU = speed (small, dear, fast).** weyland's CPU path covers capacity now; an
eGPU would add speed later.

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

# OPTION B — Ollama on rogueone's GPU  ✅ **LIVE ($0)**
**The current serving path.** `ollama` (wraps `llama.cpp`) runs on **rogueone** (RTX 5000 Ada 16 GB +
128 GB RAM). Models that fit in VRAM run fully on GPU; larger ones (30B/70B) offload the overflow
layers to the 128 GB RAM. Serves an OpenAI-compatible `/v1` API at `192.168.1.230:11434` — the harness
points at it now, no client change if the weyland eGPU (Option A) is added later.

> **History:** Option B originally ran as **CPU inference on weyland** (LXC CT-102, 96 GB RAM, $0) — the
> committed baseline that guaranteed a serving path regardless of any GPU decision. B79 (2026-07-12)
> retired CT-102 and re-homed Ollama to rogueone's GPU, freeing 32 GB to grow mother 50 → 64 GB.

**→ Full operations, the critical thread-count fix (still applies to CPU-offloaded layers), and
measured tok/s benchmarks:
[../runbooks/model-serving-ollama.md](../runbooks/model-serving-ollama.md).** (Headline: a 30B-A3B MoE
ran at **~25 tok/s** on pure CPU once tuned; GPU offload on rogueone lifts models that fit VRAM well
above that.)

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
- **Now (live):** Option B — **Ollama on rogueone's GPU** (RTX 5000 Ada 16 GB + 128 GB RAM offload).
  Gives the harness a working large-model endpoint at `192.168.1.230:11434`.
  Operating it: [../runbooks/model-serving-ollama.md](../runbooks/model-serving-ollama.md).
- **Deferred upgrade (dedicated weyland accelerator, pending pricing):** Option A — OCuLink eGPU on
  the MS-A2. Lean: used **RTX 3090 (24 GB)** (~$900–1000) for 30B-class via vLLM; **RTX A6000 (48 GB)**
  if 70B@4-bit fully on GPU (larger VRAM than rogueone's 16 GB) is a hard requirement.

## To research before deciding (the deferred bits)
- [ ] Current pricing: MS-A2 OCuLink adapter, **DEG1 vs DEG2** dock, ATX PSU, and the candidate
      cards (used market for 3090 / A6000).
- [ ] Confirm the exact **MS-A2 OCuLink adapter** part (not all Minisforum minis share one).
- [ ] Dock **cooling** for the chosen card (blower workstation vs open-air gaming).
- [ ] Pin the **target model size** (30B vs 70B) → sets the VRAM tier.
- [ ] Power budget / physical space for dock + ATX PSU next to the MS-A2.
