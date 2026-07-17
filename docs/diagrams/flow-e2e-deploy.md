# Flow (E2E) — Deploy: git push → Argo sync → rollout → verify

Cross-system thread of [flow-deploy](flow-deploy.md) and the [deploy](../demos/deploy.md) demo, followed straight
through: a manifest edit becomes a live, verified workload. Argo is pull-based (polls ~3 min, LAN-safe — no
inbound webhook). Demo: [../demos/deploy-e2e.md](../demos/deploy-e2e.md).

```mermaid
sequenceDiagram
    actor Op as Operator (laptop)
    participant GH as GitHub<br/>(weyland-lab repo)
    participant Root as weyland-root<br/>(app-of-apps)
    participant Argo as Argo CD<br/>(argocd.weyland.lab)
    participant K3s as k3s (mother)
    participant W as Target workload

    Op->>GH: push manifest change (k8s/...)
    Root->>GH: poll repo head (~3 min) or manual refresh
    Root->>Argo: reconcile child Applications
    Argo->>GH: read desired state
    Argo->>K3s: compare desired vs live → OutOfSync
    Op->>Argo: argocd app sync <app>
    Argo->>K3s: apply manifests
    K3s->>W: roll workload (RWO singletons = Recreate)
    W-->>K3s: resources Healthy
    K3s-->>Argo: Synced + Healthy
    Op->>K3s: kubectl get <kind> → new spec live
    Argo-->>Op: argocd app get → Synced + Healthy
```

**One lane, one flow:** this is the k8s GitOps path only. The image build→runtime handoff (rsync +
`docker save | k3s ctr images import`) is the sibling flow noted in [deploy](../demos/deploy.md) — a manifest
reconcile does not rebuild images. Adoption syncs land on metadata (tracking-id annotation) and do not restart
pods; spec changes roll per the app's strategy.
