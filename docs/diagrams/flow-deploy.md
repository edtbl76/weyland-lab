# Flow: Deploy / Redeploy (build↔runtime isolation)

Manual scp-based redeploy (no Compose/Ansible automation yet — deliberate until the platform stabilizes).
Images cross the build→runtime gap **only by explicit ACL** (`docker save | k3s ctr images import`) — there
is no direct build-to-runtime push. Redeploy gotcha: `scp -r` into an existing dir leaves stale source, so
verify on the box (`grep`) and copy changed files by explicit path.

```mermaid
sequenceDiagram
    participant Dev as Operator (laptop)
    participant Src as mother build host
    participant Img as Docker build
    participant K3s as k3s containerd (ctr)
    participant Dep as Deployment (kubectl)
    Dev->>Src: scp changed source by explicit path
    Dev->>Src: grep to confirm source landed (no stale tree)
    Src->>Img: docker build -t image:tag
    Img->>K3s: docker save | k3s ctr images import (ACL'd handoff)
    Dev->>Dep: kubectl set image / rollout restart
    Dep->>K3s: pull from local containerd (app-deploy path; registry.weyland.lab now exists for job images)
    K3s-->>Dep: new pod (Recreate strategy for RWO singletons)
    Dep-->>Dev: rollout status
```
