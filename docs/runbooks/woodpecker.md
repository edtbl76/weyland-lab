# B56 — Woodpecker CI Runbook — weyland (CI/CD)

Self-hosted CI/CD (Woodpecker) on k3s — the Port **CI/CD** category and the lab's first build automation.
Server + agents in ns `woodpecker`; UI at `woodpecker.weyland.lab`; GitHub OAuth login. Now a **shared build farm
running a mixed fleet** on ONE server, routed by the built-in `backend` agent label: **weyland jobs = `kubernetes`
backend** (steps run as **pods in the cluster**, so pipelines can build/deploy the weyland apps); **STUD.io jobs =
`local` backend** (steps run on **rogueone's host shell** + native docker, which carry the real
Go/Node/pyenv/Playwright toolchain). STUD.io's full CI (3 workflows) runs green on the farm as of B57b — see
[the CLI/mixed-fleet section](#studio-ci--cli-access-mixed-fleet-b57b). Chart: `woodpecker-ci/woodpecker`.

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

## STUD.io CI & CLI access (mixed fleet, B57b)
STUD.io's CI was migrated off its own local Woodpecker onto this server (B57b, proven live 2026-08-17). Key wiring:
- **Local-backend agents:** STUD.io's 4 agents (`woodpecker-agent-1..4`, systemd units on **rogueone**, registered
  `agent_id` 4–7) advertise `backend=local` and run steps on the host shell + native docker (`studio_db` on
  `/var/run/docker.sock`). Every STUD.io workflow pins `labels: {backend: local}` so it can't schedule onto a
  weyland k8s agent (an UNLABELED workflow in v3.17 can land on ANY connected agent).
- **Two LAN NodePorts** (Argo apps `woodpecker-grpc` + `woodpecker-http` in `raw-extras.yaml`) bridge the
  off-cluster agents + CLI:
  - **gRPC `192.168.1.243:30900`** (`woodpecker-grpc-lan`) — how the local agents register (h2c; trust =
    `WOODPECKER_AGENT_SECRET`).
  - **HTTP `192.168.1.243:30980`** (`woodpecker-http-lan`) — the REST/UI port for the CLI. The public URL is behind
    `traefik-forward-auth` (Keycloak), which **302-redirects Bearer API calls** to login, so `woodpecker-cli` can't
    use `woodpecker.weyland.lab`. This NodePort bypasses Traefik; trust = the caller's PAT. (Replaces the old ad-hoc
    `kubectl -n woodpecker port-forward svc/woodpecker-server 8000:80`.)
- **CLI** (`~/.local/bin/woodpecker-cli` v3.17; creds in `~/.config/studio/woodpecker-cli.env` — `WOODPECKER_SERVER=http://192.168.1.243:30980` + PAT, gitignored). Trigger + watch a STUD.io run:
```bash
. ~/.config/studio/woodpecker-cli.env; export PATH="$HOME/.local/bin:$PATH"
woodpecker-cli pipeline create edtbl76/stud.io --branch main   # runs all 3 workflows
woodpecker-cli pipeline ps  edtbl76/stud.io <N>                 # poll step state
woodpecker-cli pipeline log show edtbl76/stud.io <N> <STEP>     # tail a step log
```
- **Repo secrets on the server** (repo `edtbl76/stud.io`, events `push`,`manual`): `sonar_token`,
  `minio_svc_access_key`, `minio_svc_secret_key`. Missing/wrong-event secrets → whole-config PARSE error
  ("secret not found"), not just a failed step.
- Same LAN-webhook constraint as below applies — STUD.io runs are CLI/manual-triggered (auto-trigger = B57a).

## weyland image CI → CD (B57a)
The weyland-lab `.woodpecker.yml` builds the weyland-built images (`weyland-tool-server`, `weyland-dagster-*`,
`weyland-rag-index`, `feast-server`, `weyland-flink*`, `store-scaler`, `scan-suite`, `guardrails-structure`,
`nemo-guardrails`) and deploys them **via git**, replacing the manual `scripts/build-push-images.sh` + hand-bumped
tags. Steps: `detect-changes → build → kubeconform → deploy-handoff`.
- **git-as-seam:** CI never calls `argocd sync`. `deploy-handoff` bumps the image tag in the tracked manifests,
  pushes a branch, and opens a **PR** (`github_token` repo secret); **you merge** → Argo reconciles → rollout.
- **SoT = `scripts/ci/images.tsv`** (image → build context → tracked manifests, lockstep pairs together). The three
  step scripts are `scripts/ci/{detect-changes,build-images,open-deploy-pr}.sh`.
- **Change detection is stateless:** each manifest already carries `:git-<oldsha>`; `detect-changes` diffs the
  image's context from that SHA to HEAD and rebuilds only what changed (BuildKit registry cache makes it cheap).
- **Tags = `git-<short-sha>`** (was hand-bumped `vN`). `IfNotPresent` + a unique tag → nodes re-pull.
- **Trigger:** nightly cron `nightly-images` **01:00 NY** (`0 5 * * *` **UTC** — Woodpecker crons are UTC, see
  `schedules.md`) + manual (`woodpecker-cli pipeline create edtbl76/weyland-lab --branch main`). No LAN webhooks.
- **Build engine = a persistent `buildkitd` Deployment** (`k8s/woodpecker/buildkitd.yaml`, Argo app
  `woodpecker-buildkitd`), NOT build-in-the-step-pod. The `build` step is a thin `buildctl --addr tcp://buildkitd:1234`
  client that mounts nothing.

**Why the daemon (hard-won 2026-08-18):** daemonless BuildKit inside an ephemeral Woodpecker step pod could not do
its snapshot mounts on this k3s cluster. In order we cleared: (1) **`fs.inotify.max_user_instances` on MOTHER** — the
step pods run on mother, so raise it there (512→8192; codified `nodes/mother/host/sysctl.d/99-weyland-buildkit.conf`;
setting it on rogueone does nothing); (2) rootless BuildKit's nested userns doesn't inherit that raise; (3) privileged
needs **AppArmor-unconfined** too; (4) `/var/lib/buildkit` on the pod's nested overlay forces the `runc-native`
snapshotter, whose bind-mounts EPERM; (5) even overlayfs-on-a-real-fs-PVC + **repo `--trusted-security`** (without
which Woodpecker silently drops `privileged`), the mount **still** EPERM'd in the step pod. A long-lived buildkitd does
those mounts in its own stable mount namespace — the standard buildkit-in-k8s pattern — and moots all of the above.
The daemon is privileged + AppArmor-unconfined **in its own manifest** (accepted: internal CI daemon, ns-isolated).
- **Build-status → Port** (`ci_pipeline`) is deferred to **B63**; it needs the `port_ingest_url` secret cleared by the
  2026-08-10 DB wipe. Until then, build health is the Woodpecker run UI.

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
- STUD.io CI: 3 workflows (main · plugin-scanner · roadie) on the farm via `local`-backend agents on rogueone (B57b DONE) — `flow-woodpecker-studio-ci` + `demos/woodpecker-studio-ci.md`
- Future (B57a): real build/deploy pipelines for the **weyland images** + cron (auto-trigger); the STUD.io migration (B57b) is done
