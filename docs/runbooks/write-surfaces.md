# Runbook — write surfaces and their front doors (B209)

Every deployed service that can **change state** (launch a job, write or delete data, change config, spend money,
send a message) must say what refuses everyone else. Design and the audit behind it:
[design/write-surfaces.md](../design/write-surfaces.md). Act-path enforcement (B207):
[demos/act-guard.md](../demos/act-guard.md).

## Pieces

| Piece | Where |
|---|---|
| The declaration | `applications.yaml`: each deployed entry has `writes: true\|false`; a write surface adds `front_door:` or `accepted_gap:` when no policy covers it, and `pod_app:` when its pod's `app` label differs from the key |
| The guard | `scripts/check-write-surfaces.sh` (repo-guards; exit 0 / 1 / 2) |
| Front doors (NetworkPolicies) | B209: `k8s/dagster/netpol-webserver.yaml`, `k8s/data-mesh/store-scaler.yaml`, `k8s/realm-of-agents/netpol.yaml`, `k8s/a2a-inspector/netpol.yaml`, `k8s/mcp-servers/netpol-compositors.yaml`. B211: `k8s/woodpecker/buildkitd.yaml`, `k8s/weyland-operator/netpol.yaml`, `k8s/promptfoo/netpol.yaml`, `k8s/apisix-etcd.yaml`, `k8s/opensearch/netpol.yaml`, `k8s/data-mesh/netpol-{feast-server,nessie,trino,flink-jobmanager}.yaml`, `k8s/lightdash/trino-noauth-proxy.yaml`, `k8s/mlflow/netpol.yaml`. **Every policy on a meshed pod also admits Prometheus on 15020/15090** (the sidecar's metrics) |
| Front doors (auth) | the registry's push host (`registry-push.weyland.lab`, Traefik basic auth), forward-auth on `realm.weyland.lab` and `feast.weyland.lab` |
| Front doors (Istio) | `k8s/istio/authz-toolserver-act.yaml`, `k8s/istio/authz-guard-act.yaml` |
| Label cross-checks | `scripts/tests/write-surface-netpol.bats`, `scripts/tests/compositor-netpol.bats` |

## Check the estate

```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/check-write-surfaces.sh --list
```

Exit 0: every write surface has a policy, a front door or a tracked gap (gaps are printed every run). Exit 1 names
each defect: an open write surface, a missing or non-boolean `writes`, or a gap with no backlog item. Exit 2 means it
couldn't check (the registry is unreadable, or no policy was parsed at all).

## Add a service that takes writes

1. Set `writes: true` on its `applications.yaml` entry.
2. Give it a front door, in this order of preference:
   - **A NetworkPolicy admitting only its callers.** Use this when any caller is unmeshed (Traefik, port-agent, the
     compositors), since an Istio rule can't name an unmeshed caller. Find the callers first: the code, the manifests,
     and `istio_requests_total{destination_app="<app>"}` over 14 days. An unlisted caller breaks silently.
   - **An Istio AuthorizationPolicy** when every caller is meshed and you want identity rather than labels. Write it as
     an ALLOW list: an exact-path DENY can be slipped past with `%2F` (B207).
   - **`front_door: "<how>"`** when the app authenticates writes itself (a login, an admin token). Forward-auth on the
     ingress does not count: a pod can call the ClusterIP directly.
3. Add the policy's expected callers to `write-surface-netpol.bats`, so a label typo fails CI.
4. Run the check above, plus a live negative check: call it from a pod that isn't admitted. From a meshed pod a
   NetworkPolicy refusal is an **instant `503` from envoy, "remote connection failure"**, not a timeout. From an
   unmeshed pod it's a connect timeout.

## Live checks (run 2026-10-14 unless noted)

Refused, from `weyland-guard` (not admitted anywhere):
```
kubectl -n weyland exec deploy/weyland-guard -c weyland-guard -- python -c "import httpx; print(httpx.post('http://dagster-webserver.weyland.svc.cluster.local:3000/graphql', json={'query':'{version}'}, timeout=5).status_code)"
kubectl -n weyland exec deploy/weyland-guard -c weyland-guard -- python -c "import httpx; print(httpx.get('http://realm-of-agents.weyland.svc.cluster.local:8080/agents', timeout=5).status_code)"
```
Admitted, from `dagster-user-code` (expect `200`):
```
kubectl -n weyland exec deploy/dagster-user-code -c dagster-user-code -- python3 -c "import json,urllib.request;r=urllib.request.Request('http://dagster-webserver.weyland.svc.cluster.local:3000/graphql',data=json.dumps({'query':'{version}'}).encode(),headers={'Content-Type':'application/json'});print(urllib.request.urlopen(r,timeout=10).status)"
```
Realm's host asks for a login (expect `302` to Keycloak):
```
curl -sk -o /dev/null -w '%{http_code}\n' https://realm.weyland.lab/agents
```

## Registry: pull host and push host (B211)

`registry.weyland.lab` is the **pull** name: what every manifest, node and scanner uses. `registry-push.weyland.lab`
is the **push** name, behind Traefik basic auth. Both reach the same registry, so an image pushed to one is pulled by
the other. Clients: CI's `build` and `golden-path-smoke` steps (Woodpecker secret `registry_push_auth`, written into a
private docker config by `scripts/ci/registry-auth.sh`), and rogueone's `scripts/push-image.sh` and
`build-push-images.sh` (a one-time `docker login`).

**One-time setup, in this order.** The Woodpecker secret must exist BEFORE a pipeline that references it runs (a missing
secret fails every step).

1. Credentials into `scripts/.env` (generated, never typed or pasted):
   ```
   printf 'REGISTRY_PUSH_USER=weyland-push\nREGISTRY_PUSH_PASSWORD=%s\n' "$(openssl rand -hex 24)" >> /home/edwardmangini/IdeaProjects/weyland/scripts/.env
   ```
2. The live Secret Traefik reads (htpasswd, apr1):
   ```
   set -a && . /home/edwardmangini/IdeaProjects/weyland/scripts/.env && set +a && kubectl -n weyland create secret generic registry-push-auth --from-literal=users="$REGISTRY_PUSH_USER:$(openssl passwd -apr1 "$REGISTRY_PUSH_PASSWORD")" --dry-run=client -o yaml | kubectl -n weyland apply -f -
   ```
3. Seal it into the repo ([secrets.md](secrets.md) § Rotate / re-seal):
   ```
   kubectl -n weyland annotate secret registry-push-auth sealedsecrets.bitnami.com/managed=true --overwrite && kubectl -n weyland get secret registry-push-auth -o yaml | kubeseal --format yaml > /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/k8s/sealed-secrets/sealed/weyland__registry-push-auth.yaml
   ```
4. The CI secret:
   ```
   set -a && . /home/edwardmangini/IdeaProjects/weyland/scripts/.env && set +a && woodpecker-cli repo secret add --repository edtbl76/weyland-lab --name registry_push_auth --value "$REGISTRY_PUSH_USER:$REGISTRY_PUSH_PASSWORD" --event cron --event manual --event push
   ```
5. rogueone: the name (rogueone resolves `*.weyland.lab` through `/etc/hosts`) and a login:
   ```
   echo '192.168.1.243 registry-push.weyland.lab' | sudo tee -a /etc/hosts && set -a && . /home/edwardmangini/IdeaProjects/weyland/scripts/.env && set +a && printf '%s' "$REGISTRY_PUSH_PASSWORD" | docker login registry-push.weyland.lab -u "$REGISTRY_PUSH_USER" --password-stdin
   ```

**Phases.** Phase 1 (this change) adds the push host and moves CI and the scripts onto it; the pull host still takes
pushes. Phase 2, after a CI build has pushed through the push host: `registry.weyland.lab` becomes a GET/HEAD-only
Traefik route, and a NetworkPolicy admits only Traefik and registry-ui to the registry pod.

## Rollback

Every front door here is git → Argo with `selfHeal`, so the only durable rollback is reverting the commit (a
`kubectl delete networkpolicy` is undone within ~3 minutes). If a policy locks out a legitimate caller, add the
caller to the policy, rather than deleting the policy, and add it to the bats expectations in the same change.
