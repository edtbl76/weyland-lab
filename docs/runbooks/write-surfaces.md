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
| Front doors (NetworkPolicies) | B209: `k8s/dagster/netpol-webserver.yaml`, `k8s/data-mesh/store-scaler.yaml`, `k8s/realm-of-agents/netpol.yaml`, `k8s/a2a-inspector/netpol.yaml`, `k8s/mcp-servers/netpol-compositors.yaml`. B211: `k8s/woodpecker/buildkitd.yaml`, `k8s/weyland-operator/netpol.yaml`, `k8s/promptfoo/netpol.yaml`, `k8s/apisix-etcd.yaml`, `k8s/opensearch/netpol.yaml`, `k8s/data-mesh/netpol-{feast-server,nessie,trino,flink-jobmanager}.yaml`, `k8s/lightdash/trino-noauth-proxy.yaml`, `k8s/mlflow/netpol.yaml`. Stores outside the registry (the guard can't see them, so `write-surface-netpol.bats` pins each one's exact callers per port): `k8s/data-mesh/netpol-{redpanda,valkey,datahub-opensearch}.yaml`, `k8s/glitchtip/netpol-valkey.yaml`, and the registry pod (`k8s/registry/registry.yaml`). **Every policy on a meshed pod also admits Prometheus on 15020/15090** (the sidecar's metrics) |
| Front doors (auth) | the registry's push host (`registry-push.weyland.lab`, Traefik basic auth), forward-auth on `realm.weyland.lab` and `feast.weyland.lab`, and Ollama's token proxy on rogueone (`ollama-proxy.service`, bearer token `ollama-proxy-token`, no remote model management; B211 2026-10-22, [model-serving-ollama.md](model-serving-ollama.md) § Front door) |
| Front doors (Istio) | `k8s/istio/authz-toolserver-act.yaml`, `k8s/istio/authz-guard-act.yaml` |
| Label cross-checks | `scripts/tests/write-surface-netpol.bats`, `scripts/tests/compositor-netpol.bats` |

## Check the estate

```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/check-write-surfaces.sh --list
```

Exit 0: every write surface has a policy, a front door or a tracked gap (gaps are printed every run). Exit 1 names
each defect: an open write surface, a missing or non-boolean `writes`, or a gap with no backlog item. Exit 2 means it
couldn't check (the registry is unreadable, or no policy was parsed at all).

**Do the front doors let the notebooks in?** (2026-10-21, CI repo-guards.) A front door admits the callers its author
listed; the JupyterHub notebooks were never listed, so Trino and Valkey refused them for a week and only a by-hand run of
the whole notebook library found it. This reads every notebook's `<service>.<namespace>.svc` hosts and fails when a
NetworkPolicy selecting that Service does not admit the singleuser servers:
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/check-notebook-front-doors.sh --list
```
Exit 0: `OK — 27 notebook(s) dial 23 in-cluster service(s): 6 behind a front door that admits them, 16 with no front
door, 1 not in git (Helm-made).` (2026-10-21). Exit 1 names the notebooks, the host and the policy, with the from-entry
to add (`namespaceSelector kubernetes.io/metadata.name=jupyterhub` + `podSelector component=singleuser-server`) and its
pin in `write-surface-netpol.bats`. Exit 2: it could not check (no notebooks, a manifest or notebook that does not
parse). **Proven failing (RUN 2026-10-21):** the real tree with Trino's notebook entry removed from a scratch copy →
`20_query_trino_federation.ipynb, 40_transform_dbt_marts.ipynb, 62_eval_rag.ipynb, 72_authz_ranger.ipynb dial
trino.data-mesh, but trino-front-door-only does not admit the singleuser servers`, exit 1. What it does not cover: an
Istio AuthorizationPolicy front door, and a poll path like the no-auth proxy's `nextUri` (pinned by its own bats case).

## Add a service that takes writes

1. Set `writes: true` on its `applications.yaml` entry.
2. Give it a front door, in this order of preference:
   - **A NetworkPolicy admitting only its callers.** Use this when any caller is unmeshed (Traefik, port-agent, the
     compositors), since an Istio rule can't name an unmeshed caller. Find the callers first: the code, the manifests,
     and `istio_requests_total{destination_app="<app>"}` over 14 days. An unlisted caller breaks silently.
     **Mesh metrics never show a CI step** (an unmeshed Woodpecker pod that exists only during a pipeline): grep
     `.woodpecker.yml` and the scripts its steps run for the host, and admit a step by `woodpecker-ci.org/step`. The
     bats test "every CI step that dials a policied store" fails on one you miss (CI #363's `test-integration-datahub`).
     A short-lived pod that dials **in its first second** can be refused even when admitted (CI #364/#365, with the
     policy live and correct: k3s admits a new pod's IP a few seconds after it starts; CI #366 was refused on the first
     call and admitted on the retry 5 s later), so its first call retries, bounded, as
     `scripts/integration/datahub-redpanda-blackbox.sh` does.
   - **An Istio AuthorizationPolicy** when every caller is meshed and you want identity rather than labels. Write it as
     an ALLOW list: an exact-path DENY can be slipped past with `%2F` (B207).
   - **`front_door: "<how>"`** when the app authenticates writes itself (a login, an admin token). Forward-auth on the
     ingress does not count: a pod can call the ClusterIP directly.
3. Add the policy's expected callers to `write-surface-netpol.bats`, so a label typo fails CI.
4. Run the check above, plus a live negative check: call it from a pod that isn't admitted. From a meshed pod a
   NetworkPolicy refusal is an **instant `503` from envoy, "remote connection failure"**, not a timeout. From an
   unmeshed pod it's a connect timeout. Test with a **fresh** connection: a new policy doesn't cut one already open.
   For a store that isn't HTTP, a TCP connect proves nothing from a meshed pod (envoy accepts it), so send the
   protocol's first message with `scripts/probe-store.py` (a Valkey `PING`, a Kafka `ApiVersions`, else an HTTP `GET`):
   ```
   kubectl -n weyland exec -i deploy/weyland-guard -c weyland-guard -- python - redpanda.data-mesh.svc.cluster.local:9092 valkey.data-mesh.svc.cluster.local:6379 < /home/edwardmangini/IdeaProjects/weyland/scripts/probe-store.py
   ```
   Refused reads `REFUSED ConnectionResetError` or `DATA b'HTTP/1.1 503 …`; admitted reads `DATA b'+PONG…` or the
   Kafka response bytes.

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

**Phases.** Phase 1 added the push host and moved CI and the scripts onto it; CI #361 (2026-10-14) proved it (the images,
build cache and cosign signatures pushed through `registry-push.weyland.lab`; the golden-path smoke Jobs pulled by the
usual name). Phase 2: `registry.weyland.lab` is two GET/HEAD-only Traefik IngressRoutes (HTTP and HTTPS, since the
nodes' pull scheme lives in mother's `registries.yaml`, not in git); the push host is HTTPS-only; and a NetworkPolicy
admits only Traefik and registry-ui to the registry pod.

Check it (expect: a GET on the pull host `200`; a POST on the pull host `404`, Traefik has no router for it; the push
host `401` without credentials):
```
curl -sk -o /dev/null -w 'pull GET %{http_code}\n' https://registry.weyland.lab/v2/ && curl -sk -o /dev/null -w 'pull POST %{http_code}\n' -X POST https://registry.weyland.lab/v2/x/blobs/uploads/ && curl -sk -o /dev/null -w 'push host %{http_code}\n' https://registry-push.weyland.lab/v2/
```

## Rollback

Every front door here is git → Argo with `selfHeal`, so the only durable rollback is reverting the commit (a
`kubectl delete networkpolicy` is undone within ~3 minutes). If a policy locks out a legitimate caller, add the
caller to the policy, rather than deleting the policy, and add it to the bats expectations in the same change.
