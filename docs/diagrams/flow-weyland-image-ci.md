# Flow: weyland image CI → CD (B57a)

How a weyland-built image gets from a source change to a running pod, **decoupled via git** — Woodpecker CI never
calls `argocd sync` (that bypasses GitOps → drift). The pipeline builds + pushes a `git-<sha>` tag and opens a PR
that bumps the manifest; **you merge**, and Argo CD does the deploy. Builds run on the `kubernetes`-backend agents
(pods on mother) but delegate the actual image build to a **persistent `buildkitd` Deployment** (a thin
`buildctl` client in the step) — daemonless BuildKit couldn't do its snapshot mounts inside an ephemeral step pod
on this cluster. Change detection is stateless: each manifest already carries `:git-<oldsha>`, so only images whose
build context changed since that SHA rebuild. Triggered by a nightly **01:00 NY** cron (UTC `0 5 * * *`) + manual;
the LAN gets no push-webhooks.

```mermaid
sequenceDiagram
    participant Trg as Cron 01:00 NY / woodpecker-cli
    participant Srv as Woodpecker server
    participant Ag as k8s-backend agent (step pods, mother)
    participant BK as buildkitd (Deployment, ns woodpecker)
    participant Reg as registry.weyland.lab
    participant GH as GitHub edtbl76/weyland-lab
    participant Op as You (review + merge)
    participant Argo as Argo CD
    Trg->>Srv: trigger pipeline (kubernetes backend)
    Srv->>Ag: dispatch steps (pods on mother)
    Ag->>Ag: detect-changes — diff each image's context from its deployed git-<sha> → build plan
    Ag->>BK: build — buildctl --addr tcp://buildkitd:1234 (per changed image)
    BK->>Reg: push registry.weyland.lab/<img>:git-<sha> (+ :buildcache, overlayfs warm cache)
    Ag->>Ag: kubeconform — schema-validate the manifests that will carry the new tag
    Ag->>GH: deploy-handoff — bump manifest tag(s) → branch ci/image-bump-<sha> → open PR (github_token)
    Op->>GH: review + merge PR
    Argo->>GH: detect main changed (auto-sync)
    Argo->>Reg: (nodes) pull the new git-<sha> tag
    Argo->>Argo: reconcile → rollout the bumped Deployment(s)
    Note over Srv,Ag: notify-port (build status → Port ci_pipeline) is deferred to B63; nothing deploys unattended — the merge is the gate.
```
