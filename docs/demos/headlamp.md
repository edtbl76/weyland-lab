# Demo — Headlamp Kubernetes UI (demo by B239)

Headlamp (ns `headlamp`, Helm app) at <https://headlamp.weyland.lab>, behind Keycloak forward-auth, logging in with the
`kube-system/headlamp-admin` ServiceAccount token (cluster-admin). Operate: [runbooks/lab-uis.md](../runbooks/lab-uis.md).

## CLI walkthrough (RUN 2026-11-08)

```bash
kubectl -n headlamp get deploy headlamp
```

Seen: `headlamp 1/1`.

```bash
curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' https://headlamp.weyland.lab
```

Seen: `307` to `https://keycloak.weyland.lab/realms/weyland/protocol/openid-connect/auth?...`: the ingress answers and
the Keycloak gate is in front of it.

## UI walkthrough (eyes-on, pending the owner)

Reading the login token is a credential step, so this part is the owner's.
1. Open <https://headlamp.weyland.lab>, sign in to Keycloak.
2. Paste the `headlamp-admin` token at Headlamp's login.
3. Confirm: the cluster overview loads; Workloads → Deployments in namespace `weyland` lists the lab's deployments
   (for example `weyland-tool-server`, `dagster-webserver`), all available.

Look, do not change: Headlamp can edit live objects, and Argo reverts edits to anything it manages.

## Cleanup

None.
