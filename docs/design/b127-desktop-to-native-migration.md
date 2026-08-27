# B127 — STUD.io: Docker Desktop → Native Docker + data-plane consolidation onto weyland

**Status:** PLANNED (this doc). Executed pieces so far: B127 pre-stage (masterdb + photos backed up, native
`studio_studio_db_data` volume pre-loaded + verified — B127 steps 1–3 of the earlier data migration), and #1 below
(genre-trainer doc edits). Everything else is planned, not applied. Execution is **gated on parking the STUD.io session**
(the app stack must be quiesced for the cutover). Nothing here is staged on disk except the #1 genre-trainer edits.

## Why
Docker Desktop on rogueone runs a whole qemu/KVM Linux VM to host containers the host kernel could run directly. The
native engine (`default` context, `/var/run/docker.sock`, docker 29.7.1, nvidia runtime) already runs alongside it. B127
retires Desktop → native-only. Headline: Desktop's VM disk (`~/.docker/desktop/vms`) has ballooned to **574 GB** (qcow only
grows, never reclaims) to hold ~70 MB of real data — the migration hands back ~574 GB.

## Decisions locked (user)
- **Retire Docker Desktop; native engine becomes the only daemon on rogueone.**
- **Consolidate STUD.io's shared infra onto weyland (mother)** — "cross-contamination is not a problem": MinIO + SonarQube
  move to the central weyland instances. **masterdb stays local** on rogueone (hot-path + CI-heavy + mother is
  RAM-ceilinged) but is **backed up to weyland**.
- **Keep the 4 Woodpecker agents on rogueone** (re-pointed to weyland's server → 6 build agents total; B57).
- Rule of thumb: rogueone stops *hosting* shared infra and becomes a *client* of weyland's — left with the app stack +
  CI agents + GPU services.

## End state on rogueone
One docker daemon (native) running the STUD.io app stack (minus studio_minio, minus sonarqube/sonarqube_db, minus the
retired local woodpecker_server) + 4 local-backend Woodpecker agents (→ weyland `:30900`, B57) + existing native GPU
services (Ollama, rag-embed, ray-worker, vLLM/SGLang, genre-trainer).

---

## Workstreams

### #1 — genre-trainer → native  ✅ DONE (docs)
GPU work is on `ray-worker.service` (already native); the container is a CPU driver. Desktop was *capping* its RAM.
Edits applied: `services/genre-trainer/README.md` (both `docker run`s prefixed `DOCKER_HOST=unix:///var/run/docker.sock`
+ memory-cap note rewritten), `docs/hosts.md`, `docs/arch.md`. Effective next training run.

### #2 — SonarQube → consolidate on weyland
weyland Sonar: `svc/sonarqube` ns `weyland`, ClusterIP `:9000`, pod meshed PERMISSIVE, Argo app whole-dir-syncs
`k8s/sonarqube/`. STUD.io Sonar is wired into CI + roadie + `.mcp.json` (not idle).
1. NodePort `sonarqube-api-lan` `:30969` → Sonar `:9000` (browser stays forward-auth'd; machines use project tokens).
2. Create `controlroom` project (key must match `sonar-project.properties`) + scoped analysis token (admin creds in
   `sonarqube-secret`).
3. STUD.io repoints: `roadie/internal/pipeline/sonar.go` (`sonarURL` + `sonarDockerURL` → `http://192.168.1.243:30969`,
   remove `--network dev_default`), `.woodpecker/main.yml` (health-check → `…:30969/api/system/status`; set `sonar_token`
   secret on **weyland's** Woodpecker), `.sonar-token` (rogueone → weyland token), `.mcp.json`
   (`SONARQUBE_URL` → NodePort, remove `--network dev_default`, feed `SONARQUBE_TOKEN`).
4. Drop `sonarqube` + `sonarqube_db` + their 4 volumes from `docker-compose.dev.yml` (~10 GB RAM freed).
Tradeoff accepted: STUD.io sonar step + gate now depend on weyland being up (it's a gate, not a build blocker).

### #3 — MinIO → use weyland's, drop studio_minio
weyland MinIO: `svc/minio` ns `minio`, ClusterIP api `:9000` / console `:9001`, pod **1/1 NOT meshed** (plain HTTP, no
TLS), root creds secret `minio-creds`, Argo app whole-dir-syncs `k8s/minio/`. No standing LAN S3 endpoint today.
1. NodePort `minio-s3-lan` `:30990` → MinIO api `:9000` (HTTP; app `useSSL=false`). Console NOT exposed.
2. One-time weyland provisioning (via `mc`, root creds from `minio-creds`): buckets `studio-photos` / `studio-downloads` /
   `studio-backups`; `mc anonymous set download studio-downloads`; a **`studio` user** + policy scoped to `studio-*` only
   (tighter than global `readwrite`); load the **5 production photos** into `studio-photos` (from the B127 backup); add
   `studio-photos` + `studio-backups` to weyland's `minio-backup` mirror (root-disk redundancy).
3. STUD.io repoints (`docker-compose.yml`): `MINIO_ENDPOINT` → `http://192.168.1.243:30990` (two places: L52 + L121);
   access/secret keys → the scoped `studio` user; bucket unchanged; **remove** `studio_minio` + `studio_minio_init`
   services, `studio_minio_data` volume, `depends_on` refs, `studiominio` network alias.
4. Cleanup: delete the now-moot native `studio_studio_minio_data` volume pre-loaded during the B127 data migration.
Tradeoff accepted: STUD.io photo serving now depends on weyland MinIO being up.

### #4 — masterdb production durability (keep local + back up to weyland)
masterdb is the ONLY production data left on the laptop post-#3. "Move to weyland Postgres" ruled out: reusing
`weyland-postgres` is STRICT mTLS (external unreachable); a dedicated mother Postgres is feasible but rejected for now —
the DB is hot-path (every app request + CI clones `masterdb_test_ci_0..3` + 4 parallel e2e shards), mother is
RAM-ceilinged (~80 GiB, no swap, OOM history), and roadie's CI assumes a local `docker exec studio_db`. Revisit if
multiple products / a beefier mother arrive.
1. **Backup action:** `docker exec studio_db pg_dump -U studio -Fc masterdb | mc pipe wl/studio-backups/masterdb/masterdb-<ts>.dump`
   (consistent `-Fc` snapshot, piped — no temp file; ~1.5 MB/run, proven size from B127). Guardrails: skip cleanly if
   `studio_db` not up; verify uploaded object size >0.
2. **Schedule:** `systemd` timer, `OnCalendar=daily` + **`Persistent=true`** (laptop is often off overnight → runs at next
   boot if missed). NOT cron.
3. **Retention:** MinIO ILM rule on `studio-backups` (expire >30 days) — server-side.
4. **Redundancy:** `studio-backups` in the `minio-backup` mirror → chain = rogueone → weyland MinIO → weyland root disk
   (3 copies, none laptop-only).
5. **Monitoring:** optional Uptime Kuma push monitor pinged on success (pages via Telegram if no ping in ~26h).
Components: `scripts/backup-masterdb.sh`, gitignored `.backup.env` (scoped `studio` keys), `.service`+`.timer`, `mc` on
host PATH. Restore drill = the `pg_restore` path proven in the B127 data migration.

### #5 — DOCKER_HOST repointing
Two mechanisms reach the Desktop daemon:
- **Explicit pins (edit):** `woodpecker-agent-1..4/.env` (L7) + `woodpecker-weyland-pilot/.env` (L13) hardcode
  `unix:///home/edwardmangini/.docker/desktop/docker.sock` → change to `unix:///var/run/docker.sock`. **5 one-line edits.**
  (Explicit `DOCKER_HOST` overrides context, so these need editing regardless of the flip.)
- **Implicit (follow active context):** roadie (only mounts native `/var/run/docker.sock` for DinD; sets no `DOCKER_HOST`),
  `.mcp.json` docker runs, ad-hoc docker — all repoint at once via the context flip (`docker context use default`). No
  roadie/app code changes.

### #6 — Docker Desktop uninstall cleanup (LAST — after all verified on native; Desktop = rollback until green)
Install: deb `docker-desktop` 4.84.0 at `/opt/docker-desktop`; user service `disabled` but `active`.
1. `systemctl --user stop docker-desktop` + quit GUI.
2. `docker context use default` (the #5 implicit-repoint lever).
3. **Fix `~/.docker/config.json` BEFORE purge** — ⚠️ it has `"credsStore": "desktop"`; purge removes
   `docker-credential-desktop` → authed pulls break. Remove/replace `credsStore` + drop `"currentContext": "desktop-linux"`.
4. `sudo apt purge docker-desktop`.
5. `docker context rm desktop-linux`.
6. `rm -rf ~/.docker/desktop` → reclaims **~574 GB**. Point of no return (holds the current Desktop-resident prod volumes)
   → only after native verified + backups confirmed.
7. Verify: `docker context ls` = only `default`; `docker version` → native; app stack + agents green; `pgrep -af
   docker-desktop` empty.

---

## Execution sequencing
**Additive / non-disruptive (can stage + apply anytime, no STUD.io downtime):**
- #2 step 1 (Sonar NodePort), #3 step 1 (MinIO S3 NodePort) — push → Argo auto-syncs. Verify with `nc -vz`.
- #2 step 2 (Sonar project/token), #3 step 2 (MinIO buckets/user/photos/mirror) — weyland-side provisioning.

**Cutover batch (needs the STUD.io session parked):**
1. B127 app cutover: `compose down` on Desktop → `docker context use default` → `compose up` on native (adopts the
   pre-loaded `studio_studio_db_data`; drop studio_minio + sonarqube per #2/#3) → `roadie` re-seed + CI regenerates test DBs.
2. #2/#3 STUD.io repoints (sonar.go / .woodpecker / .mcp.json / .sonar-token / docker-compose.*).
3. #5 agent `.env` edits.
4. #4 install the backup timer.
5. Smoke-test everything on native (app, CI scan+gate, photos, backup runs).
6. #6 uninstall Desktop + reclaim 574 GB.

## Rollback
Until #6 step 6, Docker Desktop + its volumes are intact — revert = `docker context use desktop-linux` + `compose up` on
Desktop. The B127 backup (`~/Documents/Studio/backups/b127-20260813/`, checksummed) is the data floor throughout.

## Related
Weyland backlog **B127**; B57 (Woodpecker CI bridge — keeps the 4 agents, retires STUD.io's local woodpecker_server);
memory `b127-docker-native-migration`, `b57-woodpecker-studio-ci-bridge`, `stud-io-product`.
