# U12 — Tool Server Extended Health/Status Endpoints

Adds, beyond `/health`: `/ready` (readiness = embed model + pgvector), `/status`
(consolidated server+model+4 backends), `/pgvector/health` (was missing), guards
`/qdrant/health`, and wires k8s liveness (`/health`) + readiness (`/ready`) probes.
Files: services/weyland-tool-server/main.py, k8s/weyland-tool-server.yaml.

## Rebuild + redeploy

On rogueone (repo checkout) — sync code + manifest:
```bash
rsync -a nodes/mother/lab/weyland-platform/services/weyland-tool-server/main.py emangini@mother:~/lab/weyland-platform/services/weyland-tool-server/main.py
```
```bash
rsync -a nodes/mother/lab/weyland-platform/k8s/weyland-tool-server.yaml emangini@mother:~/lab/weyland-platform/k8s/weyland-tool-server.yaml
```

On mother — build, import, prune, apply (probes), restart:
```bash
docker build -t weyland-tool-server:local ~/lab/weyland-platform/services/weyland-tool-server/
```
```bash
docker save weyland-tool-server:local | sudo k3s ctr images import -
```
```bash
docker image prune -f
```
```bash
kubectl apply -f ~/lab/weyland-platform/k8s/weyland-tool-server.yaml
```
```bash
kubectl rollout status deployment/weyland-tool-server -n weyland
```

## Validate (on mother — tool server NodePort 30080)
```bash
curl -s http://localhost:30080/health | jq
```
```bash
curl -s http://localhost:30080/ready | jq
```
```bash
curl -s http://localhost:30080/pgvector/health | jq
```
```bash
curl -s http://localhost:30080/status | jq
```
```bash
kubectl get pods -n weyland -l app=weyland-tool-server
```

Expected: `/health` → status ok + version 0.2.0; `/ready` → `{"status":"ready"}` (HTTP 200);
`/status` → overall ok, `model.loaded=true`, all 4 backends ok; pod `READY 1/1` (readiness
probe passing). Negative confidence: `/status` shows a backend as `error` (not a 500) if
that backend is down, and the pod stays Ready as long as model+pgvector are fine.
