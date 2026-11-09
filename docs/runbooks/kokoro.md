# Kokoro text-to-speech — runbook

Self-hosted, OpenAI-compatible text-to-speech (`/v1/audio/speech`), the media lane's TTS. It costs nothing and has no
quota; it replaced ElevenLabs, whose free tier cannot use library voices through the API. Browser player:
<https://kokoro.weyland.lab> (Keycloak forward-auth). Demo: [demos/media-lane.md](../demos/media-lane.md). Written by
B239 (2026-11-08), which found no runbook for operating it.

## How it is built

- **Deployment** `kokoro` (ns `weyland`), image `ghcr.io/remsky/kokoro-fastapi-cpu` pinned by digest, manifest
  `k8s/kokoro/kokoro.yaml`. Service `kokoro:8880`, ingress `kokoro.weyland.lab`. CPU only, memory limit 3Gi.
- **Model:** Kokoro (~82M parameters, Apache-2.0); 68 voices on 2026-11-08 (for example `af_heart`).
- **Callers** reach it through Bifrost as the custom provider `kokoro/kokoro` ([mcp-gateway.md](mcp-gateway.md)).
- **The image is pinned by digest** (`@sha256:2ff7f4d5…`, B239, 2026-11-08: the digest that was running, with health
  and synthesis verified on it). It was `:latest` before, so a restart could pull a different version. To upgrade,
  smoke-test a new digest and change the pin.

## Is it healthy?

```bash
kubectl -n weyland get deploy kokoro
```

```bash
kubectl exec -n weyland deploy/kokoro -- python3 -c "import json,urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8880/health', timeout=10).read().decode()); v=json.load(urllib.request.urlopen('http://127.0.0.1:8880/v1/audio/voices', timeout=10)); print('voices', len(v.get('voices', v)))"
```

Expected: `{"status":"healthy"}` and `voices 68`. The readiness probe only checks that port 8880 is open (the first
boot warms the model for about 25 s), so the health call above is the real check.

**A real synthesis** (local, free, writes nothing):

```bash
kubectl exec -n weyland deploy/kokoro -- python3 -c "import json,time,urllib.request; t=time.time(); r=urllib.request.Request('http://127.0.0.1:8880/v1/audio/speech', data=json.dumps({'model':'kokoro','input':'Runbook check.','voice':'af_heart','response_format':'mp3'}).encode(), headers={'Content-Type':'application/json'}); b=urllib.request.urlopen(r, timeout=60).read(); print(len(b), 'bytes', b[:3], round(time.time()-t, 1), 's')"
```

Expected (2026-11-08): about 20,000 bytes starting `b'ID3'` (an MP3) in about 7 s on CPU.

## What broke? Symptom to cause

| Symptom | Likely cause | Check and fix |
|---|---|---|
| speech requests time out the first time after a restart | the model is still warming | wait about 25 s, then the health call |
| `OOMKilled` | a very long input on CPU, against the 3Gi limit | split the text; the logs and `describe` below |
| the running image is not the pinned one | someone edited the Deployment by hand (Argo reverts it) | `kubectl -n weyland get pod -l app=kokoro -o jsonpath='{.items[0].status.containerStatuses[0].imageID}'` against the pin in `k8s/kokoro/kokoro.yaml` |
| Bifrost callers get errors, the in-pod check works | the Bifrost provider entry | [mcp-gateway.md](mcp-gateway.md) |

## Logs and restart

```bash
kubectl -n weyland logs deploy/kokoro --tail=200
```

```bash
kubectl -n weyland rollout restart deploy/kokoro && kubectl -n weyland rollout status deploy/kokoro --timeout=180s
```

Stateless; a restart costs only the warm-up.

## Restore

Stateless: nothing to restore. The model ships in the image.
