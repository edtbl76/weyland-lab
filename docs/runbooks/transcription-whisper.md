# Whisper STT Runbook — timberback GPU (k8s app `whisper`)

Speech-to-text via **whisper.cpp**. Exposes its native `/inference` plus an OpenAI-compatible
`/v1/audio/transcriptions` shim, so Open WebUI (and any OpenAI client) uses local whisper instead of a cloud STT.

**History:** whisper ran CPU-only in LXC CT 103 on the weyland Proxmox host from 2026-06-12. B134 (plan step 2) moved it
to timberback's RTX 5070 Ti as the Argo app `whisper` (`k8s/whisper/`) on 2026-11-14. CT 103 was stopped 2026-11-15
and destroyed 2026-11-17; its code (`nodes/weyland/whisper/`) and OpenTofu record went with it (git history keeps both).

**Related:** [timberback runbook](timberback.md) (GPU sharing, VRAM budget) · code: `services/whisper-cuda/` (image),
`k8s/whisper/` (Deployment, Services, NetworkPolicy, alert).

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
- **Uptime Kuma:** monitor #16 `whisper` checks `http://10.43.142.42:9000/health`, the Service's ClusterIP, pinned in
  `whisper.yaml`. Kuma's pod resolves only LAN names (dnsPolicy None, search `weyland.lab`), so a `*.svc` name gets
  `.weyland.lab` appended and hits the wildcard; the NodePort is refused (it arrives NATed to mother's IP).
- **Cutover done 2026-11-14:** Open WebUI's STT points here (owner voice test: "it worked. WOW that is fast").

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
docker build -t registry.weyland.lab/whisper-cuda:1.9.5-3 /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/services/whisper-cuda
```

[rogueone]
```
/home/edwardmangini/IdeaProjects/weyland/scripts/push-image.sh registry.weyland.lab/whisper-cuda:1.9.5-3
```

Tags are `<whisper.cpp version>[-<rebuild>]`: `1.9.5` was the first push, `1.9.5-2` the rebuild after the shim's Sonar fixes, `1.9.5-3` (the live tag) added `libgomp1`: `1.9.5-2` crash-looped with `libgomp.so.1: cannot open shared object file`, and the build now runs `ldd` and fails on any missing library except the driver's `libcuda.so.1`. A tag is never reused: the node caches by tag (`IfNotPresent`). A new build gets the next free tag and a manifest bump in `k8s/whisper/whisper.yaml` (three image lines).

### Test it

[rogueone]
```
curl -s http://192.168.1.233:30901/v1/audio/transcriptions -F file=@/home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/services/whisper-cuda/jfk.wav -F model=whisper-1 -F response_format=json
```

Expect (measured 2026-11-14 on timberback, 0.18-0.31 s for the 11 s clip; CT 103 took about 12 s on CPU):
`{"text":"And so my fellow Americans, ask not what your country can do for you, ask what you can do for your country."}`.
The words match CT 103 exactly. CT 103 returned the same text split into three segments, so its plain text has
`\n` line breaks; the GPU decodes the clip as one segment. Compare words, not bytes.

## Consumers

### Open WebUI (recommended) — B13
The robust consumer: a browser voice/chat UI that uses **Ollama for chat** and **this shim for
voice-in** via Open WebUI's OpenAI-compatible Audio→STT setting (base URL
`http://whisper.weyland.svc.cluster.local:9000/v1` + any dummy key).
The value lives in Open WebUI's database; `scripts/open_webui_curate.py` owns it (`--check` reports drift). Stable, documented config that **fails open**
(breaks one panel, not a whole agent). ✅ **Live & validated 2026-06-12** at
`https://chat.weyland.lab` (mic → shim `POST /v1/audio/transcriptions` confirmed). Manifests:
`nodes/mother/lab/weyland-platform/k8s/open-webui/`. See backlog B13.

> OpenClaw removed 2026-07-17, to be revisited (B28).
