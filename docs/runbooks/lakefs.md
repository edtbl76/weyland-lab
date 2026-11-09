# lakeFS — runbook

Git-style versioning for the data mesh's raw files: each dataset domain is a lakeFS repository whose `main` branch
holds the landed source files (bronze), and pipeline runs commit to it. UI: <https://lakefs.weyland.lab>. Written by
B239 (2026-11-08), which found no runbook for operating it (only a secret-escrow note).

## How it is built

- **Deployment** `lakefs` (ns `data-mesh`, image `treeverse/lakefs:1.67.0`), manifest `k8s/data-mesh/lakefs.yaml`.
  Service `lakefs:8000`, NodePort `lakefs-lan` **30800**.
- **Metadata** in the data-mesh Postgres (`lakefs` database); **objects** in MinIO bucket `lakefs`
  (`minio.minio.svc:9000`, path-style).
- **Secrets:** `lakefs-secret` (data-mesh) holds the database connection string, the MinIO keys and the
  **`encrypt-key`**, which encrypts lakeFS's stored credentials in Postgres and cannot be regenerated. It is sealed in
  git (`k8s/sealed-secrets/sealed/data-mesh__lakefs-secret.yaml`), so it restores with the Sealed Secrets controller
  key ([secrets.md](secrets.md)). Clients authenticate with `lakefs-creds` (sealed in `data-mesh`, `weyland` and
  `jupyterhub`).
- **Repositories (2026-11-08):** `finance`, `health`, `music`, each with default branch `main`. Writers: the Dagster
  land and export assets ([datasets-lake.md](datasets-lake.md)). Readers also use lakeFS's S3 gateway
  (`s3://<repo>/main/...`), for example LanceDB tables.

## Is it healthy?

```bash
kubectl -n data-mesh get deploy lakefs
```

```bash
curl -s -w ' HTTP %{http_code}\n' http://192.168.1.243:30800/_health
```

Expected: `alive! <instance id> HTTP 200`. `/api/v1/healthcheck` returns `204` as well.

**The repositories and their latest commits** (read-only, using the Dagster pod's own lakeFS credentials, so none
pass through your shell):

```bash
kubectl exec -n weyland deploy/dagster-user-code -- python3 -c "import base64,json,os,urllib.request;h='http://lakefs.data-mesh.svc.cluster.local:8000/api/v1';t=base64.b64encode((os.environ['LAKEFS_ACCESS_KEY_ID']+':'+os.environ['LAKEFS_SECRET_ACCESS_KEY']).encode()).decode();g=lambda p: json.load(urllib.request.urlopen(urllib.request.Request(h+p,headers={'Authorization':'Basic '+t}),timeout=20));[print(r['id'], r['default_branch'], g('/repositories/'+r['id']+'/branches/'+r['default_branch'])['commit_id'][:10]) for r in g('/repositories?amount=100')['results']]"
```

Expected: one line per repository, `finance main …`, `health main …`, `music main …`. A missing repository, or an
authentication error, is a finding.

## What broke? Symptom to cause

| Symptom | Likely cause | Check and fix |
|---|---|---|
| `/_health` fails, pod not ready | Postgres (data mesh) or MinIO unreachable | `kubectl -n data-mesh logs deploy/lakefs --tail=100`; the store's health |
| land jobs fail writing to lakeFS | lakeFS down, or the client credentials in `lakefs-creds` are wrong | the repo listing above (it uses the same credentials) |
| `error authenticating request` on the API | no or wrong credentials | expected without credentials; use the command above |
| after a restore, lakeFS cannot read its stored credentials | the restored database does not match the `encrypt-key` | restore the sealed `lakefs-secret` with the controller key, not a new key |

## Logs and restart

```bash
kubectl -n data-mesh logs deploy/lakefs --tail=200
```

```bash
kubectl -n data-mesh rollout restart deploy/lakefs && kubectl -n data-mesh rollout status deploy/lakefs --timeout=180s
```

lakeFS keeps no state in the pod, so a restart is safe; writes in progress fail and the writing job reports it.

## Restore

The metadata database is in the data-mesh Postgres backup (`pg-backup`, daily) and the objects are in the MinIO
`lakefs` bucket; both rows are in `docs/dr.md`. Restore the sealed `lakefs-secret` first: without the matching
`encrypt-key` a restored database cannot be read.

## Related

- How data lands and moves: [datasets-lake.md](datasets-lake.md), [datasets-hydration.md](datasets-hydration.md).
  Secrets: [data-mesh-secrets.md](data-mesh-secrets.md), [secrets.md](secrets.md).
