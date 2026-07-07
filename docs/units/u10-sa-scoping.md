# U10 — Service Account Scoping (least privilege) — Apply & Validate

Finding (audit 2026-06-09): no app workload has any RBAC grant (good), but all 13
weyland/n8n pods run as the `default` ServiceAccount with an auto-mounted API token they
never use. Fix: `automountServiceAccountToken: false` on the default SA in both app
namespaces (CIS 5.1.6). Headlamp untouched (own SA, needs the API).

Manifest: `k8s/rbac-default-sa-noautomount.yaml`. Commands on mother unless noted.

> Note: the SA change only affects pods created AFTER it. Existing pods keep their token
> until restarted — so apply, then restart workloads to realize it.

---

## 1. Apply

```bash
# from repo box:
rsync -a nodes/mother/lab/weyland-platform/k8s/rbac-default-sa-noautomount.yaml \
  emangini@mother:~/lab/weyland-platform/k8s/rbac-default-sa-noautomount.yaml
# on mother:
kubectl apply -f ~/lab/weyland-platform/k8s/rbac-default-sa-noautomount.yaml
kubectl get sa default -n weyland -o jsonpath='{.automountServiceAccountToken}'; echo
kubectl get sa default -n n8n     -o jsonpath='{.automountServiceAccountToken}'; echo
```

Expected: both print `false`.

## 2. Prove it on one workload (tool server) before rolling the rest

```bash
kubectl rollout restart deployment/weyland-tool-server -n weyland
kubectl rollout status deployment/weyland-tool-server -n weyland

# token should be GONE from the new pod:
kubectl exec -n weyland deploy/weyland-tool-server -- ls /var/run/secrets/kubernetes.io/serviceaccount 2>&1
# expected: "No such file or directory" (or "cannot access")

# and it should still work:
curl -s http://localhost:30080/health | jq
```

Expected: the `ls` errors (no token dir), `/health` returns ok. App unaffected, credential gone.

## 3. Roll the rest to realize it everywhere

```bash
kubectl rollout restart deployment -n weyland   # all weyland deployments
kubectl rollout restart deployment -n n8n
# apisix-etcd is a StatefulSet:
kubectl rollout restart statefulset weyland-apisix-etcd -n weyland
kubectl get pods -n weyland; kubectl get pods -n n8n
```

Spot-check a couple of UIs afterward (e.g. `curl -sI https://n8n.weyland.lab`) to confirm
nothing regressed. (Or skip the bulk restart and let pods pick it up on their next natural
restart — the credential is removed either way for new pods.)
