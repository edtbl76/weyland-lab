# Lab UIs — runbook (the small browser tools)

Six UIs that are each a thin front end over something documented elsewhere. They share one runbook because their
operation is the same: a Deployment, an ingress behind Keycloak forward-auth (NeoDash on a NodePort instead), and a
restart if it misbehaves. Written by B239 (2026-11-08), which found none of them in a runbook. Every UI in the lab:
`docs/tools.md` and `docs.weyland.lab/tools/`.

| UI | URL | Deployment | What it is for |
|---|---|---|---|
| A2A Inspector | <https://inspector.weyland.lab> | `weyland/a2a-inspector` | validates the Realm of Agents' A2A surface and Agent Cards without dispatching ([realm-of-agents.md](realm-of-agents.md)) |
| docs-site | <https://docs.weyland.lab> | `weyland/docs-site` | the MkDocs Material site built from the public repo, with the Tools launchpad |
| Promptfoo | <https://promptfoo.weyland.lab> | `weyland/promptfoo` | the prompt-regression eval gate (B84): results UI over its `/data` PVC |
| OpenSearch Dashboards | <https://opensearch.weyland.lab> | `opensearch/opensearch-dashboards` | browse and query OpenSearch (the lexical RAG backend) |
| Headlamp | <https://headlamp.weyland.lab> | `headlamp/headlamp` | a Kubernetes web UI |
| NeoDash | <http://192.168.1.243:30088> | `weyland/neodash` | dashboards over Neo4j |

## Are they up?

```bash
for d in weyland/a2a-inspector weyland/docs-site weyland/promptfoo weyland/neodash opensearch/opensearch-dashboards headlamp/headlamp; do kubectl -n ${d%/*} get deploy ${d#*/} --no-headers; done
```

All `1/1`. From a browser-less shell, each ingress UI should redirect to Keycloak (that proves the ingress and the
gate; the app itself is behind it):

```bash
for u in inspector docs promptfoo opensearch headlamp; do printf '%-11s ' $u; curl -s -o /dev/null -m 10 -w '%{http_code}\n' https://$u.weyland.lab; done; curl -s -o /dev/null -m 10 -w 'neodash    %{http_code}\n' http://192.168.1.243:30088
```

Expected (2026-11-08): `307` for the five ingress UIs and `200` for NeoDash. A `502`/`503` from an ingress UI means
its pod is down; `404` means the ingress is missing.

## Per-UI notes

- **docs-site** builds at pod start: an initContainer clones the public repo and runs `mkdocs build`. It is rebuilt
  daily by the CronJob `docs-site-rebuild` (05:30 NY). To publish a docs change now:
  `kubectl -n weyland rollout restart deploy/docs-site`. A Mermaid block that fails to render breaks only that page;
  CI's `check-mermaid.sh` catches it before the push.
- **Promptfoo:** evals run inside the pod (`kubectl exec … promptfoo eval`) and land on its `/data` PVC; the UI
  only views them. How the eval lanes use it: [demos/eval-lanes.md](../demos/eval-lanes.md).
- **Headlamp** logs in with the token of ServiceAccount `kube-system/headlamp-admin`, which is bound to
  **cluster-admin** (`k8s/headlamp-admin-token.yaml`). Reading that token is a credential step, so it is the
  owner's. Headlamp is a write-capable cluster UI: Argo reverts live edits to Argo-managed objects (`selfHeal`), but
  use it to look, not to change.
- **OpenSearch Dashboards** reads the same OpenSearch the `rag-index-opensearch` consumer writes
  ([rag-stream.md](rag-stream.md)).
- **NeoDash** has no forward-auth (a NodePort); it connects to Neo4j with the credentials you enter.
- **A2A Inspector** is the safe way to exercise the Realm: it reads Agent Cards and checks the protocol without the
  paid dispatches a real message triggers.

## Logs and restart

The same pattern for each (namespace and name from the table):

```bash
kubectl -n weyland logs deploy/promptfoo --tail=100
```

```bash
kubectl -n weyland rollout restart deploy/promptfoo
```

All are stateless except Promptfoo, whose results are on its PVC and survive a restart.

## Restore

Nothing to restore except Promptfoo's `/data` PVC (eval history), which has no `dr.md` row; B240 (DR catalog gaps)
covers every app PVC. The others rebuild from git or hold no data.
