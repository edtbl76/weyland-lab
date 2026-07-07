# U6 — Tool Server DB Credential Hardening — Deploy & Validate

Unit U6 (Iteration 1). Change: `validate_required_secrets()` in the tool server
`main.py` — fail fast at startup if `WEYLAND_DB_PASSWORD` or `NEO4J_PASSWORD` are
missing/empty, instead of starting with a blank password and failing later.

Commands run from `mother` unless noted. Canonical rebuild commands live in
`../validation/test-commands.md` (Image Management); repeated here for a runnable sequence.

---

## 1. Sync source to mother

Run from the repo checkout:

```bash
rsync -a nodes/mother/lab/weyland-platform/services/weyland-tool-server/main.py \
  emangini@mother:~/lab/weyland-platform/services/weyland-tool-server/main.py
```

## 2. Rebuild image and import into k3s

```bash
docker build -t weyland-tool-server:local ~/lab/weyland-platform/services/weyland-tool-server/
docker save weyland-tool-server:local | sudo k3s ctr images import -
```

## 3. Redeploy

```bash
kubectl rollout restart deployment/weyland-tool-server -n weyland
kubectl rollout status deployment/weyland-tool-server -n weyland
```

---

## 4. Positive check — clean start with secrets present

Pod should reach `Running` and serve normally (secrets are mounted via secretKeyRef).

```bash
kubectl get pods -n weyland -l app=weyland-tool-server
kubectl logs -n weyland deployment/weyland-tool-server --tail=30
curl -s http://localhost:30080/health | jq
```

Expected: pod `Running`, logs show normal uvicorn startup (no RuntimeError),
`/health` responds.

---

## 5. Negative test — fail-fast on missing secret (safe, local)

Runs the same image with blank passwords. `validate_required_secrets()` fires at
import (before model load / DB connect), so the container exits immediately with
our message. **Does not touch the live cluster secret.**

```bash
docker run --rm -e WEYLAND_DB_PASSWORD= -e NEO4J_PASSWORD= weyland-tool-server:local
```

Expected: container exits non-zero with:

```
RuntimeError: Missing required secret env vars: WEYLAND_DB_PASSWORD, NEO4J_PASSWORD.
These are supplied by Kubernetes Secrets (weyland-postgres-secret, neo4j-secret)
via secretKeyRef — check that the Secrets exist in the 'weyland' namespace and are
mounted by the deployment.
```

Single-var check (only Neo4j missing):

```bash
docker run --rm -e WEYLAND_DB_PASSWORD=dummy -e NEO4J_PASSWORD= weyland-tool-server:local
```

Expected: message names only `NEO4J_PASSWORD`.

> Alternative (in-cluster, higher risk): patch `weyland-postgres-secret` to blank
> `POSTGRES_PASSWORD`, restart, observe CrashLoopBackOff via
> `kubectl logs ... --previous`, then **restore the secret**. Avoid unless you
> need to prove the secretKeyRef→empty path end to end — forgetting to restore
> breaks Postgres auth for every consumer.

---

## 6. Confirm running image carries the change

```bash
docker run --rm --entrypoint cat weyland-tool-server:local /app/main.py | grep validate_required_secrets
```
