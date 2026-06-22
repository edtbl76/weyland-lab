# B56 — Woodpecker CI Runbook — weyland (CI/CD)

Self-hosted CI/CD (Woodpecker) on k3s — the Port **CI/CD** category and the lab's first build automation.
Server + agents in ns `woodpecker`; UI at `woodpecker.weyland.lab`; GitHub OAuth login. **Kubernetes backend:**
pipeline steps run as **pods in the cluster**, so pipelines can build/deploy the weyland apps. Intended as the
shared **build farm** (Stud.IO migrates onto it later — B57). Chart: `woodpecker-ci/woodpecker`.

---

## What it is
- **woodpecker-server** (StatefulSet) — UI + orchestration (HTTP :80, gRPC :9000), SQLite at `/var/lib/woodpecker`.
- **woodpecker-agent** (×2) — pull work, spawn each step as a **k8s pod** (the chart's RBAC lets them create
  pods/PVCs in ns `woodpecker`). Server↔agent share `woodpecker-default-agent-secret` (chart-created).
- Values: `k8s/woodpecker/woodpecker-values.yaml`.

## Deploy
1. **GitHub OAuth app** (github.com → Settings → Developer settings → OAuth Apps → New): Homepage
   `https://woodpecker.weyland.lab`, callback `https://woodpecker.weyland.lab/authorize`. → Client ID + Secret.
2. Secret + namespace + cert + install:
```bash
kubectl create namespace woodpecker
kubectl create secret generic woodpecker-secret -n woodpecker \
  --from-literal=WOODPECKER_GITHUB_CLIENT='<id>' --from-literal=WOODPECKER_GITHUB_SECRET='<secret>'
# wildcard cert into the ns (ingress TLS):
kubectl get secret weyland-wildcard-tls -n weyland -o json | jq 'del(.metadata.namespace,.metadata.resourceVersion,.metadata.uid,.metadata.creationTimestamp,.metadata.managedFields,.metadata.ownerReferences)' | kubectl apply -n woodpecker -f -
helm repo add woodpecker-ci https://woodpecker-ci.org && helm repo update
helm install woodpecker woodpecker-ci/woodpecker -n woodpecker -f k8s/woodpecker/woodpecker-values.yaml
```
3. **rogueone `/etc/hosts`:** `192.168.1.243 woodpecker.weyland.lab` (it doesn't use CoreDNS; the OAuth redirect
   is browser-mediated so login works on the LAN). Then `https://woodpecker.weyland.lab` → Login → GitHub.

## The LAN trigger constraint (important)
**GitHub can't reach `woodpecker.weyland.lab`** (no public ingress), so it can't deliver push webhooks → **pushes
do NOT auto-trigger builds**. Activating a repo still works (login + repo list are outbound/browser). Trigger via
the **Run pipeline** button or **cron**. (Same wall that parked B30. To get push-triggered CI you'd expose
Woodpecker publicly or run a poller — not done.)

## Pipelines
- `.woodpecker.yml` lives at the **repo root on GitHub** (Woodpecker reads it from the forge, NOT your local
  checkout — if it's only local, the UI says "nothing to run"). Steps use the k8s backend (each step = a pod).
- `.yamllint` at the repo root tunes the `yaml-syntax` check: `extends: relaxed` + `line-length: disable`
  (80-col is meaningless for commented k8s manifests; keeps the checks that catch real breakage).

## Woodpecker → Port (CI/CD category)
A `notify-port` step (`when: status:[success,failure]`) POSTs build status to a Port webhook DS; mapped to the
**`ci_pipeline`** blueprint (id `repo-number`, so it stays unique once Stud.IO joins → build history per run).
- The Port ingest URL lives in a **Woodpecker repo secret `port_ingest_url`** (env `from_secret`) — keeps the
  ingest key OUT of the public `.woodpecker.yml`.
- Payload built with `printf` (clean JSON, no quote-escaping); fields: number/status/repo/branch/commit/event/url.

## Gotchas (hard-won)
- **YAML colon-space:** a `curl -H "Content-Type: application/json"` line in `commands` makes YAML parse it as a
  *map* (`cannot unmarshal map … into string`). Put multi-command shell in a **`|` literal block**.
- **Port webhook mapping must be Saved** before the event fires — there's **no replay**; re-run the pipeline
  after saving the mapping (first run's event is lost if the mapping wasn't saved yet).
- **Config must be on GitHub**, not just local — Woodpecker reads from the forge head.
- Benign agent log: `could not persist agent config at /etc/woodpecker/agent.conf` (agent persistence is off;
  harmless — the agent just re-registers on restart).
- Single-node k3s → `WOODPECKER_BACKEND_K8S_STORAGE_RWX: false` + `local-path` (RWO; steps run sequentially).

## Pointers
- Values: `k8s/woodpecker/woodpecker-values.yaml` · pipeline: `.woodpecker.yml` + `.yamllint` (repo root)
- Port: `ci_pipeline` blueprint + `woodpecker` webhook DS + Launcher `endpoint/woodpecker`
- Future (B57): real build/deploy pipelines for the weyland images + cron; migrate Stud.IO onto this farm
