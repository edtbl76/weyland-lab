# Weyland Platform Test Commands

All commands run from `mother` unless noted.

---

## Pod Health

```bash
kubectl get pods -n weyland
```

### Check logs

```bash
kubectl logs -n weyland deployment/weyland-tool-server --tail=50
kubectl logs -n weyland deployment/weyland-tool-server --tail=50 --previous
```

### Evict dead pods

Sweep terminal-state leftovers across the app namespaces. `status.phase=Failed` catches
`Evicted`/`Error`/`OOMKilled`; `status.phase=Succeeded` catches `Completed`. A
field-selector delete can ONLY match non-Running pods, so it can never fat-finger a live
pod (unlike a `grep | awk | xargs delete`).

```bash
for ns in n8n weyland headlamp; do
  kubectl delete pods -n $ns --field-selector=status.phase=Failed
  kubectl delete pods -n $ns --field-selector=status.phase=Succeeded
done
```

Single namespace:

```bash
kubectl delete pods -n weyland --field-selector=status.phase=Failed
kubectl delete pods -n weyland --field-selector=status.phase=Succeeded
```

---

## Tool Server

> **Host to target:** from mother use `http://localhost:30080`; from **rogueone / any other LAN
> host** use `http://mother:30080` (NodePort 30080 on mother = 192.168.1.243). Testing from
> rogueone is the real client path — it also proves the pod's own egress to Ollama (192.168.1.244)
> works end-to-end, not just from the node.

### Confirm running image

```bash
curl -s http://localhost:30080/openapi.json | jq '.paths | keys'
```

Expected routes (v0.4.0):
```
/context/ask
/context/search
/evals/leaderboard
/evals/run
/evals/runs
/evals/score
/health
/models
/neo4j/health
/ollama/health
/pgvector/health
/pipeline/trigger
/qdrant/health
/ready
/status
/weaviate/health
```

### Service health

```bash
curl -s http://localhost:30080/health | jq
curl -s http://localhost:30080/qdrant/health | jq
curl -s http://localhost:30080/weaviate/health | jq
curl -s http://localhost:30080/neo4j/health | jq
```

### Context search — all backends

```bash
curl -s -X POST http://localhost:30080/context/search \
  -H "Content-Type: application/json" \
  -d '{"query": "what model is rogueone serving", "limit": 3}' | jq

curl -s -X POST "http://localhost:30080/context/search?backend=qdrant" \
  -H "Content-Type: application/json" \
  -d '{"query": "what model is rogueone serving", "limit": 3}' | jq

curl -s -X POST "http://localhost:30080/context/search?backend=weaviate" \
  -H "Content-Type: application/json" \
  -d '{"query": "what model is rogueone serving", "limit": 3}' | jq

curl -s -X POST "http://localhost:30080/context/search?backend=neo4j" \
  -H "Content-Type: application/json" \
  -d '{"query": "what model is rogueone serving", "limit": 3}' | jq
```

### Pipeline trigger

```bash
curl -s -X POST http://localhost:30080/pipeline/trigger \
  -H "Content-Type: application/json" \
  -d '{"job_name": "weyland_ingestion_job"}' | jq
```

### LLM / RAG (B7 — Ollama at 192.168.1.244)

Check reachability first — `.llm.status` confirms pod → 192.168.1.244 routing:

```bash
curl -s http://localhost:30080/status | jq '.llm, .status'
curl -s http://localhost:30080/ollama/health | jq
curl -s http://localhost:30080/models | jq
```

RAG ask — default model (`qwen3:30b-a3b`), then a per-request model override:

```bash
curl -s -X POST http://localhost:30080/context/ask -H "Content-Type: application/json" -d '{"query": "What is the Weyland platform architecture?", "limit": 3}' | jq '{model, answer}'
curl -s -X POST http://localhost:30080/context/ask -H "Content-Type: application/json" -d '{"query": "summarize the tool server", "limit": 3, "model": "deepseek-coder-v2:16b"}' | jq '{model, answer}'
```

> First `/context/ask` after a deploy can take 10–60 s (model load + CPU generation + qwen3's
> thinking block) — that's expected, not a hang. The 300 s server-side timeout covers it; the
> model then stays resident ~5 min (`OLLAMA_KEEP_ALIVE`) so follow-up calls are fast.

#### From rogueone (external client — the real consumption path)

Same calls, swap `localhost` → `mother` (NodePort on 192.168.1.243). This validates the full chain
a harness client uses: rogueone → mother NodePort → pod → Ollama (192.168.1.244).

```bash
curl -s http://mother:30080/status | jq '.llm, .status'
curl -s -X POST http://mother:30080/context/ask -H "Content-Type: application/json" -d '{"query": "What is the Weyland platform architecture?", "limit": 3}' | jq '{model, answer}'
curl -s -X POST http://mother:30080/context/ask -H "Content-Type: application/json" -d '{"query": "summarize the tool server", "limit": 3, "model": "deepseek-coder-v2:16b"}' | jq '{model, answer}'
```

> `mother` must resolve from rogueone (`/etc/hosts` / CoreDNS LAN resolver, per U9). If it doesn't,
> use `http://192.168.1.243:30080`.

---

## Eval (B4)

Drive the eval loop + read the leaderboard via the tool-server — single-path, no kubectl/SQL. Dagster
/ Postgres internals: ../runbooks/eval-harness.md.

```bash
curl -s -X POST http://localhost:30080/evals/run | jq      # question-gen + 6-model matrix (~40-60 min CPU)
curl -s -X POST http://localhost:30080/evals/score | jq    # judge-panel score latest run (~70 min, 3 judges)
curl -s http://localhost:30080/evals/runs | jq             # list recent runs
curl -s http://localhost:30080/evals/leaderboard | jq      # panel leaderboard (latest scored run)
curl -s "http://localhost:30080/evals/leaderboard?run_id=3" | jq   # a specific run
```

---

## Image Management

### Confirm image content

```bash
docker run --rm --entrypoint cat weyland-tool-server:local /app/main.py | grep "pipeline"
```

### Check k3s image

```bash
sudo k3s ctr images ls | grep tool-server
```

### Rebuild and redeploy

```bash
docker build -t weyland-tool-server:local ~/lab/weyland-platform/services/weyland-tool-server/
docker save weyland-tool-server:local | sudo k3s ctr images import -
docker image prune -f   # reclaim the now-dangling previous build (prevents disk creep)
kubectl apply -f ~/lab/weyland-platform/k8s/weyland-tool-server.yaml   # ONLY when the manifest changed (env/probes/service)
kubectl rollout restart deployment/weyland-tool-server -n weyland
kubectl rollout status deployment/weyland-tool-server -n weyland
```

> Note: mother runs workloads in k3s/containerd, NOT docker — docker here is only a
> build tool. Every `save | ctr import` leaves the prior docker image dangling, so the
> `docker image prune -f` above keeps `/var/lib/docker` from ballooning (it hit 88% once).
> containerd self-GCs unreferenced images, so no manual cleanup needed there.
>
> The `kubectl apply` is only needed when the **manifest** changed (e.g. the B7 `OLLAMA_*`
> env). For a code-only change (`main.py`), `rollout restart` alone re-pulls the freshly
> imported image. `rollout restart` does NOT re-read the manifest — so don't skip the apply
> when env/probes changed.

---

## Dagster

### Check pods

```bash
kubectl get pods -n weyland | grep dagster
```

### Open UI

```
http://mother:30088
```

---

## Qdrant

```bash
curl -s http://localhost:30083/collections | jq
```

---

## Weaviate

```bash
curl -s http://localhost:30087/v1/.well-known/ready
curl -s http://localhost:30087/v1/schema | jq
```

---

## Neo4j

```bash
curl -s http://localhost:30085/db/data/ | jq
```

---

## SCP (from rogueone)

Sync changed tool-server files to mother before rebuilding. Run from the repo root on rogueone.
Only scp what actually changed.

main.py — code (almost every change):
```bash
scp nodes/mother/lab/weyland-platform/services/weyland-tool-server/main.py emangini@mother:~/lab/weyland-platform/services/weyland-tool-server/main.py
```

Manifest — only when k8s/env changed (e.g. the B7 `OLLAMA_*` vars); pair with `kubectl apply`:
```bash
scp nodes/mother/lab/weyland-platform/k8s/weyland-tool-server.yaml emangini@mother:~/lab/weyland-platform/k8s/weyland-tool-server.yaml
```

Dockerfile — only when dependencies changed:
```bash
scp nodes/mother/lab/weyland-platform/services/weyland-tool-server/Dockerfile emangini@mother:~/lab/weyland-platform/services/weyland-tool-server/Dockerfile
```
