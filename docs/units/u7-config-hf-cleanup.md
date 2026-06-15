# U7 — Tool Server Config & HF Cache Cleanup — Deploy & Validate

Unit U7 (Iteration 1). Changes (Dockerfile only; `main.py` unchanged):
- Removed the dead `ENV` config block (deployment yaml is now the single source of
  truth; `main.py` keeps in-cluster DNS defaults for standalone runs).
- Pinned `HF_HOME=/app/.cache/huggingface`; added `HF_HUB_OFFLINE=1` +
  `TRANSFORMERS_OFFLINE=1` *after* the build-time model download so runtime never
  reaches the HF hub.

Commands run from `mother` unless noted. Rebuild commands mirror `../validation/test-commands.md`.

---

## 1. Sync source to mother

```bash
scp nodes/mother/lab/weyland-platform/services/weyland-tool-server/Dockerfile \
  emangini@mother:~/lab/weyland-platform/services/weyland-tool-server/Dockerfile
```

## 2. Rebuild — the build IS the offline-ordering test

```bash
docker build -t weyland-tool-server:local ~/lab/weyland-platform/services/weyland-tool-server/
```

Expected: build succeeds. The model download at the `RUN python -c ...` layer happens
*before* the offline flags are set — a green build confirms the ordering. (If offline
flags came first, this layer would fail trying to fetch offline.)

## 3. Import + redeploy

```bash
docker save weyland-tool-server:local | sudo k3s ctr images import -
kubectl rollout restart deployment/weyland-tool-server -n weyland
kubectl rollout status deployment/weyland-tool-server -n weyland
```

---

## 4. Confirm offline env baked into the image

```bash
docker run --rm --entrypoint env weyland-tool-server:local | grep -E 'HF_|OFFLINE'
```

Expected: `HF_HOME=/app/.cache/huggingface`, `HF_HUB_OFFLINE=1`,
`TRANSFORMERS_OFFLINE=1`. Confirm the old `WEYLAND_DB_*` / `QDRANT_*` etc. defaults
are GONE from the image:

```bash
docker run --rm --entrypoint env weyland-tool-server:local | grep -E 'WEYLAND_DB|QDRANT_|WEAVIATE_|NEO4J_|DAGSTER_' || echo "OK: no baked config defaults"
```

## 5. Runtime proof — model loads offline + search works

Pod reaching Ready already implies the embed model loaded under offline flags (it
loads at startup in lifespan). Confirm end to end:

```bash
kubectl get pods -n weyland -l app=weyland-tool-server
kubectl logs -n weyland deployment/weyland-tool-server --tail=30
curl -s http://localhost:30080/health | jq
curl -s -X POST http://localhost:30080/context/search \
  -H "Content-Type: application/json" \
  -d '{"query": "what model is rogueone serving", "limit": 3}' | jq '.results[0]'
```

Expected: pod `Running`, no HF network errors in logs, `/health` ok, and the search
returns a result (embedding ran offline against the baked model). Note the response
shape is `{"query": ..., "results": [...]}` — index `.results[0]`, not `.[0]`.
