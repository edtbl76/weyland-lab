# U11 — weyland-lab SSH Identity Review

Review outcome: the `weyland-lab` SSH key was shared by **Dagster** (active — reads
weyland.md from rogueone) and **n8n** (legacy ingestion, retired). Decision: don't mint
per-service keys — **remove n8n's copy** so it's single-purpose, then harden Dagster's use.

- **(done) De-share:** removed the SSH key volume/mount from `k8s/n8n/n8n.yaml`.
- **(b) Host-key pin:** `source_document.py` now pins rogueone's ed25519 host key
  (`WEYLAND_SSH_HOST_KEY` env in user-code.yaml) and uses `RejectPolicy` — no more blind
  `AutoAddPolicy` (MITM closed). **Fail-closed:** if rogueone's host key rotates, update
  `WEYLAND_SSH_HOST_KEY` or ingestion's `source_document` step will fail.
- **(c) FUTURE = U18:** lock the key on rogueone's authorized_keys (restrict/from/forced
  command) — needs switching source_document SFTP→exec. See units-iter1.md.

Get rogueone's host key: `ssh-keyscan -t ed25519 rogueone` (the `AAAA…` blob).

---

## Deploy (b) — rebuild user-code + redeploy

```bash
# from repo box: sync code + manifest
scp nodes/mother/lab/weyland-platform/services/weyland-dagster/weyland_pipeline/assets/source_document.py \
  emangini@mother:~/lab/weyland-platform/services/weyland-dagster/weyland_pipeline/assets/source_document.py
scp nodes/mother/lab/weyland-platform/k8s/dagster/user-code.yaml \
  emangini@mother:~/lab/weyland-platform/k8s/dagster/user-code.yaml

# on mother: rebuild user-code image, import, prune, redeploy
docker build -t weyland-dagster-user-code:local ~/lab/weyland-platform/services/weyland-dagster/
docker save weyland-dagster-user-code:local | sudo k3s ctr images import -
docker image prune -f
kubectl apply -f ~/lab/weyland-platform/k8s/dagster/user-code.yaml
kubectl rollout restart deployment/dagster-user-code -n weyland
kubectl rollout status deployment/dagster-user-code -n weyland
```

## Validate — the host-key pin must still let ingestion read the file

```bash
# trigger a run (source_document runs first, exercising the SSH read even if hash-gate skips writes)
curl -s -X POST http://localhost:30080/pipeline/trigger \
  -H "Content-Type: application/json" -d '{"job_name": "weyland_ingestion_job"}' | jq

# confirm source_document succeeded (NO host-key rejection)
kubectl logs -n weyland deploy/dagster-user-code --tail=100 \
  | grep -iE 'source_document|paramiko|host key|known_hosts|reject|SSHException|error' || echo "no SSH errors in tail"
```

Authoritative check: open the run in the Dagster UI (`https://dagster.weyland.lab` from
rogueone) — `source_document` should be green. A pin failure shows as a paramiko
host-key/`RejectPolicy` error on that step.

> Negative confidence (optional): a wrong `WEYLAND_SSH_HOST_KEY` value makes
> `source_document` fail with a host-key error — proof the pin is actually enforced.
