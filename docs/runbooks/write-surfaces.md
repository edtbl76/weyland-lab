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
| Front doors (NetworkPolicies) | `k8s/dagster/netpol-webserver.yaml`, `k8s/data-mesh/store-scaler.yaml`, `k8s/realm-of-agents/netpol.yaml`, `k8s/mcp-servers/netpol-compositors.yaml` |
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

## Rollback

Every front door here is git → Argo with `selfHeal`, so the only durable rollback is reverting the commit (a
`kubectl delete networkpolicy` is undone within ~3 minutes). If a policy locks out a legitimate caller, add the
caller to the policy, rather than deleting the policy, and add it to the bats expectations in the same change.
