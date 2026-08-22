# IaC — Argo CD (GitOps) Runbook — weyland

GitOps CD for the weyland **k8s** layer: Argo CD reconciles cluster state from the public `weyland-lab` repo.
The deploy flow is now **edit → push to GitHub → Argo reconciles** (the rsync-to-mother loop is retired for
onboarded apps). UI at `argocd.weyland.lab`. ns `argocd`. Pairs with OpenTofu (which owns the non-k8s lanes —
Proxmox, SaaS). Part of the IaC track (B58).

---

## What it is
- Installed via helm (`argo/argo-cd`, chart 9.6.0). `configs.params.server.insecure: true` — Traefik
  terminates TLS, so the server runs HTTP internally (avoids Argo's own-TLS redirect loop). dex + notifications
  off (local admin; OIDC via Keycloak comes with the data mesh / B1). Values: `k8s/argocd/argocd-values.yaml`.
- **Pull-based** — Argo polls the repo (~3 min) + on manual refresh. **No inbound webhook needed → LAN-safe**
  (unlike Woodpecker push-CI; see [[lan-no-github-webhooks]]).
- **app-of-apps:** a root Application (`k8s/argocd/root-app.yaml`, **auto-sync, prune OFF**) watches
  `k8s/argocd/applications/` and creates one child Application per app. Adding an app = commit an Application
  there. Children carry **no resources-finalizer** → removing a child file never cascade-deletes a real app.

## The onboarding pattern (brownfield-safe)
1. Add an Application **observe-only** (no `syncPolicy.automated`) → it shows Healthy + **OutOfSync** and
   touches nothing.
2. Open **DIFF**. For a clean brownfield app the only diff is Argo adding `argocd.argoproj.io/tracking-id`
   (annotation-based tracking — lands on resource metadata, NOT the pod template → **sync does not restart pods**).
3. **Sync** = pure adoption (stamps ownership, goes green). Then flip to `automated: {selfHeal, prune}` once trusted.

## Apps onboarded (79)
- **Raw** (20, auto-sync): open-webui + subdir apps (`dagster`, `glitchtip`, `minio`, `mlflow`, `n8n`,
  `sonarqube`, `unleash`, `uptime-kuma`, `litellm`) + loose-file apps via include-globs (`postgres`, `qdrant`,
  `weaviate`, `neo4j`, `neodash`, `weyland-tool-server`, `apisix`) + raw-extras (`loki-rules`,
  `monitoring-extras`, `opencost-ingress`). Files: `applications/{subdir,loose}-apps.yaml`, `raw-extras.yaml`.
- **Helm** (8, multi-source — chart from helm repo + values from git via `$values`): `loki`, `alloy`, `tempo`,
  `kube-prometheus-stack`, `opencost`, `woodpecker`, `keda`, `keda-http-add-on`. File: `applications/helm-apps.yaml`.
- **NOT onboarded (deliberate — still running, just not GitOps-tracked):** istio (istioctl), argocd (self),
  port-agent (Port outbound-polling action agent), traefik/coredns/rbac (k3s system), code-quality (run-once Jobs); **headlamp deferred**.

## Hard-won gotchas
- **Server-Side Apply for big CRDs.** keda `scaledjobs` + kube-prometheus-stack `prometheuses`/`alertmanagers`
  CRDs exceed the 256 KB `last-applied-configuration` annotation under client-side apply →
  `metadata.annotations: Too long`. Fix = `syncPolicy.syncOptions: [ServerSideApply=true]` (SSA doesn't write
  that annotation). Set on **all** helm apps.
- **Helm→Argo adoption shows a bigger diff** than raw apps (Argo swaps Helm's `managed-by` metadata for its
  tracking) — expected; do helm syncs **deliberately, one at a time**, not all-at-once blind.
- **`releaseName` must match the LIVE helm release** or chart-templated names diverge → duplicates. The
  kube-prometheus-stack release is literally named **`monitoring`**, not `kube-prometheus-stack`.
- **Multi-source helm-with-git-values:** one source = the chart (`chart:` + `targetRevision:` = chart version),
  the other = the git repo with `ref: values`; the chart's `helm.valueFiles` reference `$values/<path-in-repo>`.
- **`server.insecure: true`** behind Traefik (TLS terminated at the ingress) — else redirect loops.
- **Config must be on GitHub**, not just local — Argo reads the repo head (a local-only file → "nothing to sync").

## Operate (CLI — programmatic; use this, NOT the UI)
Drive Argo with the `argocd` CLI on mother — never hand-patch the Application CRD with `kubectl patch` (the
`operation:null` / label-selector tricks silently no-op) and never fall back to UI click-paths.
- **Login** (server runs HTTP behind Traefik → `--insecure --grpc-web`):
  `argocd login argocd.weyland.lab --username admin --password "$(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d)" --insecure --grpc-web`
- **Status / diff:** `argocd app get <app>` · `argocd app diff <app>`
- **Refresh (re-pull git head) + sync:** `argocd app sync <app>` (add `--prune` to remove orphans)
- **Unwedge a stuck sync** — symptom: SYNC STATUS sits on *"waiting for healthy state of …"* and a changed
  Secret/configmap shows **OutOfSync** but never applies, because a deployment that can't go healthy blocks the
  running operation, and `another operation is already in progress` rejects any new sync. Fix:
  `argocd app terminate-op <app>` then `argocd app sync <app> --replace --prune --force`.
  `terminate-op` clears the blocking operation; `--replace` **recreates** resources (so the deployment re-rolls
  against the new Secret checksum instead of a no-op patch). This is the canonical "remove the blocker FIRST"
  move — do NOT just re-sync on top of a wedged op.

## Operate (other)
- Admin password: `kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d`
- Onboard: drop an Application in `k8s/argocd/applications/`, push → `weyland-root` creates it (`argocd app get weyland-root --refresh` to pull now).
- Pin chart versions to deployed (`helm list -A`) when writing a helm Application.

## Pointers
- `k8s/argocd/` (values, ingress, root-app, applications/) · UI `argocd.weyland.lab`
- Sibling lanes: Woodpecker CI ([runbooks/woodpecker.md](woodpecker.md)) — CI→CD handoff via git is **B57**;
  OpenTofu (Proxmox + SaaS) is the other IaC lane (B58).
