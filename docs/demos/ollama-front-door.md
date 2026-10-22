# Demo — the Ollama front door (B211, 2026-10-22)

**What it shows:** rogueone's Ollama refuses a cluster pod that has no token, serves every caller that sends the
`ollama-proxy-token` bearer token, and never lets a remote caller pull, delete or create models, token or not.
**Why it exists:** the firewall admitted mother, and every pod reaches rogueone as mother, so "only mother" meant any
pod could call Ollama, including `/api/pull` and `/api/delete`.
Flow: [flow-ollama-front-door.md](../diagrams/flow-ollama-front-door.md). Runbook:
[model-serving-ollama.md § Front door](../runbooks/model-serving-ollama.md#front-door--token-proxy-b211-2026-10-22).

**Read-only.** Nothing is created: the pull and delete below are refused before Ollama sees them (step 5 confirms the
model count). No teardown.

## CLI walkthrough (RUN 2026-10-22)

**1. A pod with no token is refused.** `weyland-guard` is admitted by nothing:
```
kubectl -n weyland exec deploy/weyland-guard -c weyland-guard -- python -c "import httpx; print(httpx.get('http://192.168.1.230:11434/api/tags', timeout=10).status_code)"
```
```
401
```

**2. A caller with the token is served**, on Ollama's native API and the OpenAI-style one. tool-server reads its own
`OLLAMA_API_KEY` (from the `ollama-proxy-token` Secret) inside its pod, so the token never leaves it:
```
kubectl -n weyland exec deploy/weyland-tool-server -c weyland-tool-server -- python -c "import os,httpx; h={'Authorization':'Bearer '+os.environ['OLLAMA_API_KEY']}; print(httpx.get('http://192.168.1.230:11434/api/tags', headers=h, timeout=10).status_code, httpx.get('http://192.168.1.230:11434/v1/models', headers=h, timeout=10).status_code)"
```
```
200 200
```

**3. Model management is refused even with the token** (the negative case that matters most):
```
kubectl -n weyland exec deploy/weyland-tool-server -c weyland-tool-server -- python -c "import os,httpx; h={'Authorization':'Bearer '+os.environ['OLLAMA_API_KEY']}; print(httpx.post('http://192.168.1.230:11434/api/pull', headers=h, json={'model':'tinyllama'}, timeout=10).status_code, httpx.request('DELETE','http://192.168.1.230:11434/api/delete', headers=h, json={'model':'qwen2.5:7b'}, timeout=10).status_code)"
```
```
403 403
```

**4. The proxy log names every caller and its status, never the token:**

[rogueone]
```
docker logs --since 3m ollama-proxy 2>&1 | grep -E '^[0-9]' | awk -F'"' '{split($3,a," "); print a[1], $2, "|", $6}' | sort | uniq -c | sort -rn
```
```
      3 200 GET / HTTP/1.1 | Uptime-Kuma/1.23.17
      1 403 POST /api/pull HTTP/1.1 | python-httpx/0.28.1
      1 403 DELETE /api/delete HTTP/1.1 | python-httpx/0.28.1
      1 401 GET /api/tags HTTP/1.1 | python-httpx/0.28.1
      1 200 GET /v1/models HTTP/1.1 | python-httpx/0.28.1
      1 200 GET /api/tags HTTP/1.1 | python-httpx/0.28.1
```
A 401 from `192.168.1.243` outside a deliberate test is a caller missing the token.

**5. Nothing was pulled or deleted**, and rogueone's own processes still reach Ollama with no token:

[rogueone]
```
curl -s localhost:11434/api/tags | python3 -c "import json,sys; print(len(json.load(sys.stdin)['models']), 'models')"
```
```
14 models
```

**6. The proxy against a real Ollama, before any deploy** (a throwaway `ollama/ollama:0.31.2` behind the repo config,
with a 64-hex token of the real shape):

[rogueone]
```
bash /home/edwardmangini/IdeaProjects/weyland/nodes/rogueone/ollama-proxy/test-proxy.sh
```
Expect 9 `ok` lines and `OK — the proxy admits only the token from a remote source and never forwards model management.`

**7. The firewall rules for :11434 and :8765 are in place, in order:**

[rogueone]
```
sudo bash /home/edwardmangini/IdeaProjects/weyland/nodes/rogueone/ufw/rogueone-ufw.sh --check
```
```
OK — 2 port(s), 3 allow rule(s) and their denies in place, in order.
```

## UI walkthrough + UAT

1. **Open WebUI** (`https://chat.weyland.lab`): start a chat with an Ollama model (for example `qwen2.5:7b-operator`).
   **Confirm** it answers. Its key is the connection key under Admin Panel → Settings → Connections → Ollama API (the
   gear on `http://192.168.1.230:11434`). RUN 2026-10-22: 4 chats answered, all `200` in the proxy log.
2. **Uptime Kuma** (`https://kuma.weyland.lab`): the Ollama monitor. **Confirm** it is green and its Headers hold the
   bearer token. RUN 2026-10-22: `200` on every probe since 18:37:51 (before the header was added it read 401).
3. **MLflow AI Gateway** (`https://mlflow.weyland.lab/#/gateway`): open `ollama-qwen25-7b` and send a message.
   **Confirm** a reply. RUN 2026-10-22: answered `ok` once its `ollama-local` secret was rotated.

## What went wrong on the way (kept so the next rollout avoids it)

- The first flip failed: nginx's default map hash bucket could not hold the real 71-character key. The test used a short
  fake token and passed. The test now mints a real-shape token, and the runbook pre-flights `nginx -t` with the real one.
- The MLflow gateway kept its old key: its script rotates an existing secret only when named in
  `GATEWAY_ROTATE_SECRETS`.
- Uptime Kuma's monitor and Bifrost's model-list refresh also called Ollama from mother. Kuma got the header. Bifrost's
  `ollama` provider was retired (no virtual key used it, and its key cannot be an env reference).
