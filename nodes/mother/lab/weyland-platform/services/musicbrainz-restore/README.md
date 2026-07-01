# musicbrainz-restore — mbslave runner

Loads the native MusicBrainz `mbdump` into the dedicated `musicbrainz-postgres` instance
(`k8s/data-mesh/musicbrainz-postgres.yaml`) using [mbslave](https://github.com/acoustid/mbslave) — the
lightweight pure-Python MB mirror tool (no MusicBrainz Perl server stack). This is the "Postgres" cell of the
storage grid, the only dataset (MusicBrainz) that ships as a real normalized relational DB.

## Why this shape (evolvable, not throwaway)

Three artifacts are **permanent** from smoke test → production, unchanged:
1. the dedicated Postgres **instance** (`musicbrainz-postgres.yaml`),
2. this **runner image**,
3. the **k8s Job** that runs it (`musicbrainz-restore-job.yaml`).

The only thing that moves is **how the dump arrives** — env-configured:
- **Now (smoke + first prod):** `mbslave init` auto-downloads the latest dump from MetaBrainz.
- **Later:** a Dagster land asset lands the dump → MinIO (freshness-gated, same pattern as the other land
  jobs), and the Job points mbslave at the MinIO-staged files instead of fetching. Same image, same Job, one
  env change. `mbslave sync` (needs a free MetaBrainz token) is the eventual incremental-freshness option.

## Config (all via env — set by the Job from `musicbrainz-postgres-secret`)

`MBSLAVE_DB_HOST` · `MBSLAVE_DB_PORT` · `MBSLAVE_DB_NAME` · `MBSLAVE_DB_USER` · `MBSLAVE_DB_PASSWORD` ·
`MBSLAVE_DB_ADMIN_USER` · `MBSLAVE_DB_ADMIN_PASSWORD` (superuser — `init` uses it to create the user + database).

## Smoke test

Build the image, deploy the instance, run the Job (see the top-level run steps / `runbooks/`). Watch the Job
logs: **schema creation + the first `COPY`s landing = the mechanism is validated** even before the full
(multi-hour) import completes. Unknowns the smoke shakes out: mbslave's current-dump compatibility, whether it
needs the `cube`/`earthdistance` extensions pre-created, and its download/scratch behavior.
