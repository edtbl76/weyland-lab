# U8 — Headlamp Permanent Admin Token — Apply & Validate

Unit U8 (Iteration 1). Goal: stop the constant Headlamp token-expiry re-login. Mints a
permanent (non-expiring) cluster-admin ServiceAccount token; paste into Headlamp once.

Manifest: `k8s/headlamp-admin-token.yaml` (ServiceAccount + ClusterRoleBinding to
cluster-admin + service-account-token Secret).

**Reframe note:** RL #5 was filed under "security hardening," but the real intent is
lab *convenience*. This deliberately creates a non-rotating cluster-admin credential —
acceptable for a single-operator LAN lab only.

Commands run from `mother` unless noted.

---

## 1. Sync + apply the manifest

```bash
# on the repo box: sync
rsync -a nodes/mother/lab/weyland-platform/k8s/headlamp-admin-token.yaml \
  emangini@mother:~/lab/weyland-platform/k8s/headlamp-admin-token.yaml

# on mother: apply
kubectl apply -f ~/lab/weyland-platform/k8s/headlamp-admin-token.yaml
```

Expected: serviceaccount, clusterrolebinding, and secret all `created`.

## 2. Confirm the token Secret is populated

```bash
kubectl get secret headlamp-admin-token -n kube-system -o jsonpath='{.data.token}' | wc -c
```

Expected: a large number (non-empty). If 0, the token controller hasn't filled it yet —
wait a few seconds and retry.

## 3. Prove the token is PERMANENT (no expiry claim)

Decode the JWT payload and check there is no `exp` field:

```bash
kubectl get secret headlamp-admin-token -n kube-system -o jsonpath='{.data.token}' \
  | base64 -d \
  | cut -d. -f2 \
  | base64 -d 2>/dev/null | jq 'has("exp")'
```

Expected: `false` (no `exp` claim = does not expire). Contrast with
`kubectl create token`, whose JWT has an `exp`.

## 4. Prove the token has full admin

```bash
kubectl auth can-i '*' '*' --as=system:serviceaccount:kube-system:headlamp-admin
```

Expected: `yes`.

## ⚠️ Gotcha — RBAC name collision with the Helm chart

The Headlamp Helm chart owns a `ClusterRoleBinding` named **`headlamp-admin`** (binding
its pod SA `headlamp/headlamp` to cluster-admin). Do NOT name our binding that — `helm
upgrade` will reclaim it and silently unbind our SA, leaving the permanent token
authenticated-but-powerless. Our binding is therefore named **`weyland-headlamp-admin`**
(see k8s/headlamp-admin-token.yaml). General rule: if `kubectl apply` says **`configured`**
(not `created`) on an object you didn't author, you're sharing ownership — use a distinct
`weyland-`prefixed name.

If access breaks after a Headlamp `helm upgrade`, check:
```bash
kubectl get clusterrolebinding weyland-headlamp-admin -o wide
kubectl auth can-i '*' '*' --as=system:serviceaccount:kube-system:headlamp-admin   # expect yes
```

## 5. Use it in Headlamp

Print the token to paste into the Headlamp login screen:

```bash
kubectl get secret headlamp-admin-token -n kube-system -o jsonpath='{.data.token}' \
  | base64 -d; echo
```

Open Headlamp (NodePort on mother), paste the token, log in. It should persist across
sessions (stored in the browser) and never prompt for re-login due to expiry.
