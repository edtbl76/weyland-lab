# n8n — deployment + workflow export

`n8n.yaml` deploys n8n; `workflows.json` is the exported workflow definition, committed so the instance is
reproducible from git (B69 completeness: "n8n workflows → git").

## What's in `workflows.json`

**One workflow: `Ingest Weyland Obsidian ReadMe` — `active: false`, i.e. RETIRED, not broken.**
It SSH'd to rogueone, read an Obsidian note, chunked it, hash-compared against `/context/source-state`, and POSTed
to `/context/ingest` on the tool-server (15-min schedule trigger). That ingestion role was **superseded by the
B-RAG-STREAM pipeline** (Dagster `rag_stream_produce` → Redpanda `rag.chunks` → 5 store consumers), which does the
same job with change-detection via the `rag_manifest` table. Kept as history + a working example of the
SSH → transform → tool-server pattern. Don't re-activate it expecting it to be the live ingest path.

## What is NOT in here (deliberately)

- **Credentials.** The export carries only a credential *reference* (`sshPrivateKey`), never the material —
  n8n keeps that in its Postgres DB, encrypted with `N8N_ENCRYPTION_KEY`. `export:credentials` is a separate
  command and its output must NEVER be committed.
- **`encryption-key.txt`.** ⚠️ That file is currently tracked in this directory and is a live security item —
  see **B97**. It is `.gitignore`d, but .gitignore does not untrack an already-tracked file. It must leave the
  git index AND the key must be rotated (the repo is public; removal does not unpublish it).

## Re-export after changing a workflow

```
kubectl -n n8n exec deploy/n8n -- n8n export:workflow --all --pretty > workflows.json
```

Before committing, confirm nothing secret rode along in node parameters (n8n *can* embed literals in a node even
though credentials live separately):

```
grep -ci "password\|token\|apikey\|secret" workflows.json    # expect 0
```
