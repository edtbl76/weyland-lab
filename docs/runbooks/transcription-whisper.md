# B11 — Whisper STT Runbook — weyland (CT 103)

Speech-to-text on weyland's CPU via **whisper.cpp**. Pure CPU, no GPU.
Exposes its native `/inference` plus an OpenAI-compatible `/v1/audio/transcriptions` shim so
the tool server / any OpenAI client can use local whisper instead of a cloud STT.

**Related:** [B7 Ollama runbook](model-serving-ollama.md) (same LXC pattern) · code:
`nodes/weyland/whisper/` (`shim.py`, `whisper-server.service`, `whisper-shim.service`).

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
