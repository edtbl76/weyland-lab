# Whisper STT Runbook — timberback GPU (k8s app `whisper`), replacing CT 103

Speech-to-text via **whisper.cpp**. Exposes its native `/inference` plus an OpenAI-compatible
`/v1/audio/transcriptions` shim, so Open WebUI (and any OpenAI client) uses local whisper instead of a cloud STT.

**Moving (B134 plan step 2, 2026-11-14):** from CPU-only CT 103 on the weyland Proxmox host to timberback's RTX 5070 Ti
as the Argo app `whisper` (`k8s/whisper/`). The two run side by side until the new one is verified; then Open WebUI
switches, CT 103 is stopped, and about a week later destroyed. The CT sections further down describe the old host until
then.

**Related:** [timberback runbook](timberback.md) (GPU sharing, VRAM budget) · code: `services/whisper-cuda/` (image),
`k8s/whisper/` (Deployment, Services, NetworkPolicy, alert) · legacy CT code: `nodes/weyland/whisper/`.

## On timberback (k8s app `whisper`)

- **Pod:** one Deployment pinned to timberback, two containers from one image: `whisper-server` (native, port 8080,
  `ggml-large-v3` on the GPU, one of 4 time-slices) and `shim` (OpenAI-compatible, port 9000). `Recreate` strategy.
- **Model:** on the PVC `whisper-models` (local-path, so it lives on timberback). The `fetch-model` init container
  downloads `ggml-large-v3.bin` (3.1 GB) once from `huggingface.co/ggerganov/whisper.cpp` and checks its SHA-256
  (`64d182b4…94d1e2`) on every start.
- **In-cluster:** `http://whisper.weyland.svc:9000/v1` (OpenAI) and `:8080/inference` (native).
- **From rogueone:** `http://192.168.1.233:30901/v1` and `:30881/inference` — the `whisper-lan` NodePort is
  `externalTrafficPolicy: Local` (keeps rogueone's IP for the NetworkPolicy), so it answers on timberback's address.
- **Who may call it:** NetworkPolicy `whisper-callers-only` admits Open WebUI, Uptime Kuma and rogueone (`192.168.1.230/32`).
- **Alert:** `WhisperDown` (warning) when the Deployment has no ready replica for 10 minutes.

### The image (`registry.weyland.lab/whisper-cuda:<whisper.cpp version>`)

Built from `services/whisper-cuda/Dockerfile`: whisper.cpp **v1.9.5** (commit checked at build) compiled for
compute capability 12.0 on NVIDIA's CUDA 12.8.1 images (pinned by digest), plus the shim and its locked Python
dependencies (`requirements.txt`, compiled from `requirements.in` with `uv pip compile --exclude-newer`). Hand-tagged, not
in `scripts/ci/images.tsv`: it changes only on a whisper.cpp or dependency bump. The upstream CUDA image was rejected:
a rolling tag, and no kernels for this GPU's architecture.

Build and push (on rogueone: the nvcc build needs more memory than mother can spare; list the tags first and never
reuse one):

[rogueone]
```
docker build -t registry.weyland.lab/whisper-cuda:1.9.5-2 /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/services/whisper-cuda
```

[rogueone]
```
/home/edwardmangini/IdeaProjects/weyland/scripts/push-image.sh registry.weyland.lab/whisper-cuda:1.9.5-2
```

Tags are `<whisper.cpp version>[-<rebuild>]`: `1.9.5` was the first push, `1.9.5-2` the rebuild after the shim's Sonar fixes (the live tag). A tag is never reused: the node caches by tag (`IfNotPresent`). A new build gets the next free tag and a manifest bump in `k8s/whisper/whisper.yaml` (three image lines).

### Test it

[rogueone]
```
curl -s http://192.168.1.233:30901/v1/audio/transcriptions -F file=@/home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/services/whisper-cuda/jfk.wav -F model=whisper-1 -F response_format=json
```

Expect exactly what CT 103 returned for the same clip on 2026-11-14 (in about 12 s on CPU):
`{"text":"And so my fellow Americans,\n ask not what your country can do for you,\n ask what you can do for your country."}`.

# Legacy: CT 103 on the weyland host (until retired)

---

**Live since 2026-06-12.** Unprivileged LXC `whisper` (CTID **103**) on the weyland Proxmox host.
- **Address:** `192.168.1.246` (DHCP-reserved).
  - `/inference` (native whisper.cpp) → `http://192.168.1.246:8080/inference`
  - `/v1/audio/transcriptions` (OpenAI shim) → `http://192.168.1.246:9000/v1`
- **Spec:** 8 cores · 8 GB RAM · 15 GB rootfs on `local-zfs` (NVMe) · `nesting=1` (Debian 12).
- **Model:** `ggml-large-v3` (~3 GB, max accuracy; CPU is fast enough that turbo isn't needed).

## Access
Through the Proxmox host (no direct login): `ssh emangini@weyland` → `pct enter 103` → `root@whisper`.
One-offs: `pct exec 103 -- <cmd>`. Files in from the host: `pct push 103 <host-file> <ct-path>`.

## Create the container (on weyland host)
```bash
pct create 103 local:vztmpl/debian-12-standard_12.12-1_amd64.tar.zst --hostname whisper --unprivileged 1 --rootfs local-zfs:15
pct set 103 --net0 name=eth0,bridge=vmbr0,ip=dhcp
pct set 103 --cores 8 --memory 8192 --swap 0 --onboot 1 --features nesting=1
pct start 103
pct exec 103 -- ip -4 addr show eth0     # note the DHCP IP (192.168.1.246); IPv4 lands a few s after start
```

## Build whisper.cpp (inside CT 103)
```bash
apt update && apt install -y build-essential cmake git curl ffmpeg
git clone https://github.com/ggml-org/whisper.cpp
cd whisper.cpp
cmake -B build
cmake --build build -j --config Release      # -> build/bin/{whisper-server,whisper-cli}
sh ./models/download-ggml-model.sh large-v3   # ~3 GB -> models/ggml-large-v3.bin
```
cmake auto-detects AVX-512/FMA on the 9955HX. `ffmpeg` lets the
server accept mp3/m4a/etc. (whisper wants 16 kHz mono WAV internally).

## Quick CLI transcription (one-off, no server)
```bash
./build/bin/whisper-cli -m /root/whisper.cpp/models/ggml-large-v3.bin -f samples/jfk.wav
```
Handy for ad-hoc/local files; the server below is for the API path.

## whisper-server (native /inference)
Validated foreground run (CPU only — log shows `no GPU found`, `CPU total size = 3094.36 MB`):
```bash
./build/bin/whisper-server -m models/ggml-large-v3.bin --host 0.0.0.0 --port 8080 -t 4
```
Native test (multipart upload → `{"text": ...}`):
```bash
curl 127.0.0.1:8080/inference -F file=@samples/jfk.wav -F response_format=json
```
> The native server exposes **only** `/inference` (and `/load`) — **no** `/v1/audio/transcriptions`.
> That's what the shim below adds.

## OpenAI-compatible shim (/v1/audio/transcriptions)
Code: `nodes/weyland/whisper/shim.py` — a ~40-line FastAPI adapter that forwards uploads to
`/inference` and returns a **strict** OpenAI response (`{"text": ...}`). Strictness matters:
some OpenAI clients fall back *silently* on response-shape drift, so the shim asks whisper for plain
text and builds the JSON itself — no stray fields.

**Deploy (3 files from `nodes/weyland/whisper/`).** On rogueone (repo root), stage to the host
(**weyland is accessed as `root`**, unlike mother which is `emangini`):
```bash
rsync -a nodes/weyland/whisper/shim.py nodes/weyland/whisper/whisper-server.service nodes/weyland/whisper/whisper-shim.service root@weyland:~/
```
On the weyland host, push into CT 103:
```bash
pct exec 103 -- mkdir -p /root/whisper-shim
pct push 103 /root/shim.py /root/whisper-shim/shim.py
pct push 103 /root/whisper-server.service /etc/systemd/system/whisper-server.service
pct push 103 /root/whisper-shim.service /etc/systemd/system/whisper-shim.service
```
Inside CT 103 — Python venv + deps, then enable both services (stop the foreground server first):
```bash
apt install -y python3-venv
python3 -m venv /root/whisper-shim/venv
/root/whisper-shim/venv/bin/pip install fastapi uvicorn httpx python-multipart
systemctl daemon-reload
systemctl enable --now whisper-server
systemctl enable --now whisper-shim
systemctl status whisper-server whisper-shim --no-pager
```

## Test the OpenAI path
Inside CT 103 (then from rogueone via `http://192.168.1.246:9000`):
```bash
curl 127.0.0.1:9000/v1/audio/transcriptions -F file=@/root/whisper.cpp/samples/jfk.wav -F model=whisper-1 -F response_format=json
```
Expect strict `{"text":" And so my fellow Americans, ask not what your country can do for you..."}`.

## Consumers

### Open WebUI (recommended) — B13
The robust consumer: a browser voice/chat UI that uses **Ollama for chat** and **this shim for
voice-in** via Open WebUI's OpenAI-compatible Audio→STT setting (base URL
`http://192.168.1.246:9000/v1` + any dummy key). Stable, documented config that **fails open**
(breaks one panel, not a whole agent). ✅ **Live & validated 2026-06-12** at
`https://chat.weyland.lab` (mic → shim `POST /v1/audio/transcriptions` confirmed). Manifests:
`nodes/mother/lab/weyland-platform/k8s/open-webui/`. See backlog B13.

> OpenClaw removed 2026-07-17, to be revisited (B28).

## TODO / tuning
- [x] DHCP-reserve `192.168.1.246` on the router (done 2026-06-12).
- [x] CoreDNS + rogueone `/etc/hosts`: `whisper.weyland.lab` → 192.168.1.246 (done 2026-06-12).
- [ ] Benchmark real-time-factor on a long clip; tune `-t` in `whisper-server.service` if useful.
