# Runbook — rogueone hard freezes (GPU VRAM overcommit on the no-iGPU laptop)

## Symptom
**rogueone** (RTX 5000 Ada mobile, 16GB, **NO iGPU**) hard-freezes — total lockup, requires holding the power
button. Happened multiple times/day; correlated with GPU/model load (e.g. driving eval / RAG traffic that loads a
big Ollama model). The `journalctl -b -1` tail just **stops mid-stream with no panic/oops** — a hard hang the kernel
couldn't even record. Don't look for a crash message; look at *what was loaded on the GPU*.

## Root cause — VRAM overcommit at model load
rogueone has **no iGPU**, so the desktop shares the compute GPU: `nvidia-smi` shows **Xorg (~1.5GB) + gnome-shell +
browser + rag-embed** all resident on GPU0 (~3.2GB baseline). `gpt-oss:20b` (the operator/eval/RAG generator on
rogueone Ollama) is **~13–14GB loaded**. Model (14GB) + display (3.2GB) = **>16GB → VRAM overcommit when the model
loads → the display gets starved / the GPU wedges → hard freeze.**

**Contributing (durable) fault:** the NVIDIA **open** kernel module (`595.71.05`) can't negotiate CPU↔GPU power/thermal
with the laptop SBIOS — every boot logs `NVRM ... PlatformRequestHandler failed to get target temp / platform power
mode from SBIOS`. No power/thermal arbitration under combined CPU+GPU load → occasional **corrected** thermal MCEs
(`mce: [Hardware Error]: Machine check events logged` — sporadic, ~1 per few days, *not* a DIMM storm) and worse hang
behavior. The MCE is a watch-item, not the acute cause.

## The fix that stops the freeze (config, no reboot)
Ollama's `OLLAMA_GPU_OVERHEAD` reserves VRAM Ollama will **not** allocate, forcing partial CPU offload so a big model
can never starve the display. It was set to **1.5GiB — too low** (display needs ~3.2GB), so Ollama loaded the model
fully on GPU and overcommitted. Raised to **6GiB**:

- File: `/etc/systemd/system/ollama.service.d/gpu-guardrails.conf` → `Environment="OLLAMA_GPU_OVERHEAD=6442450944"`
  (6GiB). Then `sudo systemctl daemon-reload && sudo systemctl restart ollama`.
- Other guardrails already there: `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_KEEP_ALIVE=30s`.

**Verify:** `ollama run gpt-oss:20b "say hi" >/dev/null 2>&1 & sleep 25; ollama ps; nvidia-smi --query-gpu=memory.used,memory.total --format=csv`
- Want: `ollama ps` shows a **CPU/GPU split** (e.g. `21%/79% CPU/GPU`), not `100% GPU`; `nvidia-smi` **~14.9GB / 16GB**
  (under the ceiling), not pinned at ~16GB. Before the fix it overcommitted to ~16.2GB → freeze.
- Trade: generation is slightly slower (some layers on CPU). Fine on a homelab.

**The reserve lever tops out** ~1.5GB of real slack here (bigger reserve just offloads more to CPU without buying much
headroom, because the display footprint floats). Enough to kill the load-time overcommit. For a *fat* margin the real
lever is a **smaller generator model** (see below).

## Durable follow-ups (pick as needed)
- **Swap NVIDIA open → proprietary driver** — restores the SBIOS thermal/power handshake the open module is failing at
  (should also quiet the thermal MCEs). Needs a driver reinstall + reboot.
- **Run a smaller RAG/operator model** that fits fully on GPU with headroom (e.g. an ~8B, ~5GB) — no CPU offload, faster
  *and* safer. Quality tradeoff vs the B66 `gpt-oss:20b` pick → decide with B66/B84.
- **Watch the MCEs** — install `rasdaemon` (decode future MCEs) + `lm-sensors` (CPU temp under load). Sporadic corrected
  errors today; if they climb, it's hardware (repaste / RMA), and no driver/config fix helps.

## Fast triage next time it freezes
```
journalctl --list-boots | tail -5                                   # is the previous boot retained?
journalctl -b -1 -k --no-pager | grep -iE "NVRM|Xid|mce|Hardware Error|thermal|oom-kill"
nvidia-smi                                                          # display + model must stay < 16GB
for b in -1 -2 -3; do echo "== $b =="; journalctl -b $b -k --no-pager | grep -iE "machine check|Hardware Error"; done
```
Key facts: RTX 5000 Ada, 16376 MiB, **no iGPU**; display baseline ~3.2GB; `gpt-oss:20b` ~14GB; keep
`memory.used < ~15GB`. Related: [[remote-training-rogueone]], [[b79-ollama-moved-mother-64gb]], [[node-oom-forensics]].
