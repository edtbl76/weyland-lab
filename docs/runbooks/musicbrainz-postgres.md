# MusicBrainz Postgres — the native mirror (data-mesh Tier-2, "Postgres" grid cell)

The **only** dataset in the storage grid that targets Postgres, because MusicBrainz is the one source that
ships as a real normalized relational database. We load the **full native `mbdump`** (all ~200 tables, FKs,
the `link` relationship graph) — not the flattened HF silver — into a **dedicated `postgres:18` instance**,
isolated from the core weyland Postgres (a 100GB mirror has no business sharing the DB Keycloak/Nessie/lakeFS
depend on).

**Loaded 2026-07-01:** artist 2.9M · release 5.6M · recording 39.3M · work 2.8M · link 1.1M.

## What it is

- **Instance:** `musicbrainz-postgres.data-mesh.svc:5432` (`k8s/data-mesh/musicbrainz-postgres.yaml`) —
  `postgres:18` (MB's server **requires 18+**; InitDb hard-rejects older), 80Gi PVC, un-meshed, `Recreate`.
- **Database `musicbrainz_db`**, schema **`musicbrainz`** (+ cover_art_archive, statistics, wikidocs, …).
- **Creds:** `musicbrainz`/`musicbrainz` (a **SUPERUSER** — needs it to create the DB + cube/earthdistance
  extensions; the password matches mbdocker's `default/postgres.env` default). Superuser alt: `postgres`/`weyland_dev_password`.
- **Connect (IntelliJ):** forward the `musicbrainz-postgres` svc :5432 via the k8s plugin → `localhost:<port>`,
  db `musicbrainz_db`, user `musicbrainz`, schema `musicbrainz`. Native Postgres introspection → the tree browses
  (unlike GizmoSQL, see [[gizmosql-datagrip-tree-browse-limitation]]).

## Why musicbrainz-docker, NOT mbslave

Community **mbslave is stale** — its newest schema support is MB schema 29 (2024-05); a current dump is newer,
so its `isrc` (and other) table DDL mismatches the dump → COPY dies (`invalid input syntax … column edits_pending`).
Skipping drifted tables would drop/corrupt data. So we use **MusicBrainz's own tooling** (musicbrainz-docker),
which by definition always matches the live schema. We use only its **image** (built once on mother), not its
compose stack — the import runs as a k8s Job against our external instance.

## How the import runs

- **Image:** built from `~/musicbrainz-docker` on mother (`admin/configure with alt-db-only-mirror` →
  `docker compose build musicbrainz`), tagged `musicbrainz-mb-import:local`, `docker save | k3s ctr import`.
- **Job:** `k8s/data-mesh/musicbrainz-restore-job.yaml` runs `recreatedb.sh -fetch` (env-configured to our
  instance). Dumps land on the **`musicbrainz-dbdump` PVC** (cached across re-runs — no re-download).
- **Refresh:** re-run the Job (`recreatedb.sh` DROPs + re-imports). CronJob-ify later. ~38 min import.

```
kubectl -n data-mesh delete job musicbrainz-import --ignore-not-found && kubectl apply -f ~/musicbrainz-restore-job.yaml && kubectl -n data-mesh logs -f job/musicbrainz-import
```

## Gotchas (every one cost a cycle)

1. **`docker compose` missing on mother** → `apt install docker-compose-plugin` (needed only for the one-time image build).
2. **Interactive licence prompt** — `fetch-dump.sh` asks "commercial/non-commercial?" and dies on EOF in a
   non-TTY container. Skip it by pre-creating the marker: the Job's args `touch /media/dbdump/.for-non-commercial-use && exec recreatedb.sh -fetch`.
3. **Istio sidecar** — data-mesh uses **revision-based** injection, so the pod **label** `sidecar.istio.io/inject: "false"` disables it (the *annotation* is ignored).
4. **`createdb.sh` isn't idempotent** ("schema/collation already exists") → use **`recreatedb.sh`** (DROPs first).
5. **`recreatedb.sh`'s raw `psql` needs `PGPASSWORD`** (it doesn't read `POSTGRES_PASSWORD` like InitDb's DBD::Pg) → set `PGPASSWORD` env too.
6. **`DROP DATABASE … being accessed by other users`** — kill sessions first, and don't leave IntelliJ connected during a re-run:
   `psql -U postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='musicbrainz_db' AND pid <> pg_backend_pid();"`
7. **PostgreSQL 18+ required** — stock `postgres:16` fails InitDb's version gate.
8. **GitOps/rsync miss** — editing the manifest but not re-`rsync`ing to mother → `kubectl apply` used the stale copy (kept us on `postgres:16`). Always re-ship after an edit ([[feedback-kubectl-runs-on-mother]]).

## Verify

```
kubectl -n data-mesh exec deploy/musicbrainz-postgres -- psql -U postgres -d musicbrainz_db -c "SELECT count(*) FROM musicbrainz.recording;"
```

## Open (completeness gate)

Loaded ✅ · Runnable ~ (Job; CronJob refresh TODO) · **Documented** ✅ (this) · Cataloged ▢ (DataHub emit) ·
Monitored ▢ (instance-down PrometheusRule) · Pushed ▢. Related: [[data-mesh-b1.2-storage]], [[postgres-strict-needs-mesh]].
