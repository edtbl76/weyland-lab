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

```bash
kubectl delete pods -n weyland --field-selector=status.phase=Failed
kubectl get pods -n weyland | grep -E 'Error|Evicted|OOMKilled' | awk '{print $1}' | xargs kubectl delete pod -n weyland
```

---

## Tool Server

### Confirm running image

```bash
curl -s http://localhost:30080/openapi.json | jq '.paths | keys'
```

Expected routes:
```
/context/search
/health
/neo4j/health
/pipeline/trigger
/qdrant/health
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
kubectl rollout restart deployment/weyland-tool-server -n weyland
```

> Note: mother runs workloads in k3s/containerd, NOT docker — docker here is only a
> build tool. Every `save | ctr import` leaves the prior docker image dangling, so the
> `docker image prune -f` above keeps `/var/lib/docker` from ballooning (it hit 88% once).
> containerd self-GCs unreferenced images, so no manual cleanup needed there.

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

Sync tool server files to mother before rebuilding:

```bash
scp nodes/mother/lab/weyland-platform/services/weyland-tool-server/main.py \
  emangini@mother:~/lab/weyland-platform/services/weyland-tool-server/main.py

scp nodes/mother/lab/weyland-platform/services/weyland-tool-server/Dockerfile \
  emangini@mother:~/lab/weyland-platform/services/weyland-tool-server/Dockerfile
```
