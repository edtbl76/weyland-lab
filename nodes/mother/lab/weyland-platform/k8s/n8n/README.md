# n8n — deployment + workflow export

`n8n.yaml` deploys n8n; `netpol.yaml` is its front door; `workflows/` and `workflows.json` are exported workflow
definitions, committed so the instance is reproducible from git (B69 completeness: "n8n workflows → git"). Argo
applies `*.yaml` only (`argocd/applications/subdir-apps.yaml`), so the JSON exports are never treated as manifests.

n8n keeps its state in **SQLite** on PVC `n8n-data` (`/home/node/.n8n`); no database env is set, so the
"Postgres" this README used to claim was never true (corrected 2026-11-04, U14). Recovery: [docs/dr.md](../../../../../../docs/dr.md) § n8n.

## The workflows

| File | Workflow | State |
|---|---|---|
| `workflows/alert-to-linear.json` | **`alert-to-linear (U14)`** (`U14alertToLinear`): critical Alertmanager alert → Linear incident, opened, closed and reopened by fingerprint | **live** — install, test and change it with [docs/runbooks/alert-to-linear.md](../../../../../../docs/runbooks/alert-to-linear.md) |
| `workflows.json` | `Ingest Weyland Obsidian ReadMe` | `active: false`, RETIRED, not broken |

The retired one SSH'd to rogueone, read an Obsidian note, chunked it, hash-compared against `/context/source-state`,
and POSTed to `/context/ingest` on the tool-server (15-min schedule trigger). That role was **superseded by the
B-RAG-STREAM pipeline** (Dagster `rag_stream_produce` → Redpanda `rag.chunks` → 5 store consumers). Kept as history
and an example of the SSH → transform → tool-server pattern; don't re-activate it expecting the live ingest path.

## Who can reach it

NetworkPolicy `n8n-front-door-only` admits only Traefik (the UI, behind Keycloak forward-auth) and the Alertmanager
pods (the incident webhook) on 5678. n8n webhooks are unauthenticated by design, so this policy is their gate.

## What is NOT in here (deliberately)

- **Credentials.** An export carries only a credential *reference* (id + name), never the material — n8n keeps that in
  its SQLite DB, encrypted with `N8N_ENCRYPTION_KEY`. `export:credentials` output must NEVER be committed. On import,
  a reference whose id is unknown is re-bound **by name**, which is why the restore path creates the credential first.
- **`encryption-key.txt`.** Gitignored and untracked since **B97** (2026-07-22). It had been committed to the public
  repo before that; rotation was considered and **declined** (B97's record says why). The live key is Secret
  `n8n-secret`.

## Re-export after changing a workflow

Export to a file inside the pod, never to stdout: n8n prints `Error tracking disabled …` on stdout before the JSON,
which corrupts a redirected export (found 2026-11-04). For `alert-to-linear`, use the runbook's command. For the
retired one:

```
kubectl -n n8n exec deploy/n8n -- n8n export:workflow --id=YgxNUxYF3wwuhSJm --pretty --output=/tmp/workflows.json && kubectl -n n8n exec deploy/n8n -- cat /tmp/workflows.json > workflows.json
```

Before committing, confirm nothing secret rode along in node parameters (n8n *can* embed literals in a node even
though credentials live separately):

```
grep -ciE "lin_api|password|token|apikey|secret" workflows.json    # expect 0
```
