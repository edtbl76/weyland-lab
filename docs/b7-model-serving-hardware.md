# B7 — Model Serving Hardware (DECISION DEFERRED — pending pricing)

**Status:** 🟡 OPEN. The *architecture* is settled; the *GPU purchase* is **deferred** until
pricing is researched. This doc captures every option + exact hardware so the decision can be
made cold later without re-deriving anything.

---

## Decision status — what's settled vs open
- **Settled:** weyland (MS-A2) is the **dedicated large-model host**; rogueone stays the
  GPU/vLLM host for small fast models. weyland was purchased *specifically* to host large
  models for harness engineering.
- **Open (deferred):** *how* weyland serves large models — **eGPU (which card?)** vs
  **CPU-only** vs **cloud**. Pending price research + digestion.

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

# OPTION A — OCuLink eGPU on weyland  *(recommended direction)*

Kit: OCuLink adapter + DEG1/DEG2 dock + ATX PSU + one GPU below. Serve via **vLLM** (VFIO
passthrough). **Baseline for comparison = rogueone's laptop RTX 5000 Ada: 16 GB / ~576 GB/s.**

### Candidate GPUs — exact models (pick by VRAM target + budget)
> Prices are **approximate street/used, mid-2026 — VERIFY current** (you're pricing this out).
> "BW" = memory bandwidth (sets token-gen speed). Cooling matters in an enclosed dock:
> **blower/workstation** cards exhaust out the back (dock-friendly); **open-air gaming** cards
> dump heat inside the dock.

#### 16 GB tier — ⚠️ NOT recommended (no VRAM gain over your laptop)
| Exact model | VRAM | BW | CUDA | Arch | TDP | Cooling | ~Price | Notes |
|---|---|---|---|---|---|---|---|---|
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

# OPTION B — CPU inference on weyland  *(no new hardware, $0)*
`llama.cpp` / `ollama` on the 96 GB RAM. Fits **70B @ 4-bit (~40 GB)** comfortably.
- Speed (memory-bandwidth-bound on DDR5): **~30B@4-bit a few tok/s, 70B@4-bit ~1–2 tok/s.**
- Good as a **$0 stopgap** and for non-interactive/batch harness runs; painful for interactive.
- Serves an OpenAI-compatible API via ollama, so it drops into the harness now and can be
  swapped for a GPU later with no client changes.

# OPTION C — Cloud GPU  *(no capex, opex + data leaves LAN)*
Rent on demand (RunPod / Vast.ai / Lambda) for occasional heavy 70B runs. Against the LAN-lab
ethos for always-on use, and recurring cost — but zero hardware and instantly any size.

---

## Why an eGPU is an upgrade over rogueone's laptop GPU
| GPU | VRAM | BW | ≈ token-gen vs laptop | ~Price |
|---|---|---|---|---|
| RTX 5000 Ada **Laptop** (rogueone, baseline) | 16 GB | 576 GB/s | 1.0× | — |
| RTX 3090 | 24 GB | 936 GB/s | ~1.6× | ~$700–900 |
| RTX 4090 | 24 GB | 1008 GB/s | ~1.75× | ~$1500–2000 |
| RTX A6000 | 48 GB | 768 GB/s | ~1.3× | ~$3000–4500 |
A 3090 is **faster *and* bigger** than the laptop card. The laptop's limit is **VRAM (16 GB)**,
not speed — so the upgrade goal is primarily VRAM (fit 30B/70B), with a speed bump as a bonus.

---

## Lean recommendation (for when the decision is taken)
- **Default:** used **RTX 3090 (24 GB)** on an OCuLink dock (~$900–1000) → 30B-class via vLLM.
- **If true 70B@4-bit on GPU is a hard requirement:** **RTX A6000 (48 GB)** (~$3k+).
- **Interim while deciding:** Option B (CPU inference, $0) — get a 70B running today, slowly.

## To research before deciding (the deferred bits)
- [ ] Current pricing: MS-A2 OCuLink adapter, **DEG1 vs DEG2** dock, ATX PSU, and the candidate
      cards (used market for 3090 / A6000).
- [ ] Confirm the exact **MS-A2 OCuLink adapter** part (not all Minisforum minis share one).
- [ ] Dock **cooling** for the chosen card (blower workstation vs open-air gaming).
- [ ] Pin the **target model size** (30B vs 70B) → sets the VRAM tier.
- [ ] Power budget / physical space for dock + ATX PSU next to the MS-A2.
