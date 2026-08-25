# pr-lifecycle — the delivery-pipeline watchdogs

**Three** CronJobs share the `pr-lifecycle` Argo app (`k8s/pr-lifecycle/`). None deploys anything. Two
answer the same question about the ship loop — **did the thing that was supposed to happen, happen?** —
and the third cleans up after it.

| CronJob | Schedule (NY) | Asks | Acts |
|---|---|---|---|
| `cron-freshness-check` | 04:30 daily | is the Woodpecker `nightly-images` cron enabled, with a future `next_exec`? | alert `ScheduledWorkNotRunning` (critical) |
| `port-pr-reconcile` | 05:15 daily | does Port still believe a closed PR is open? | **DELETES** the stale entity |
| `pr-staleness-check` | 05:45 daily | is a PR sitting open past its age budget? | alert `OpenPullRequestStale` (warning) |

The two watchdogs POST a synthetic alert to the **Alertmanager v2 API**, which needs no routing change —
the top-level route is a catch-all to `telegram`.

> ⚠ **`port-pr-reconcile` is the odd one out and the dangerous one.** The other two only ever emit an
> alert; their worst failure is a missed page. This one issues
> `DELETE /v1/blueprints/githubPullRequest/entities/<id>` against the live catalog, so its worst failure
> is deleting real data because GitHub returned a 502. Read
> [Reaping stale Port PR entities](#reaping-stale-port-pr-entities-b144) before changing anything in it.

## Why these are CronJobs and not PrometheusRules

**There is no metric for either question.** No exporter in this cluster describes a GitHub pull
request, and a **Woodpecker cron is not a Kubernetes object** — no CronJob, no Job, no pod, so
kube-state-metrics cannot see it and no `kube_cronjob_*` metric will ever cover it. The only place
the truth lives is each system's API, so the job asks it directly.

Everything that *does* have a metric is covered the normal way, by the sibling `PrometheusRule` at
`k8s/monitoring/cron-freshness-rules.yaml` — see [Coverage](#coverage) below.

## The failure these exist to catch

`nightly-images` was created `enabled: false` on 2026-08-18 and **never fired until 2026-08-22**,
while `docs/schedules.md` documented it as running daily. Four days, and nothing in the estate could
have said otherwise: all 41 alert rules watched things that *were* running. The closest exception,
`DataMeshBackupFailed`, fires on `kube_job_status_failed > 0` — a job that ran and **failed**, never a
job that never ran.

A disabled cron is completely silent: no builds, no errors, no Kubernetes object. The only tell is a
`next_exec` in the past.

## Coverage

`cron-freshness-rules.yaml` covers every **k8s** CronJob, with per-cadence budgets read from each
job's own manifest:

| Cadence | Jobs | Budget |
|---|---|---|
| every 30m | `dagster-freshness-check` | 2h |
| every 6h | `lancedb-sync` | 8h |
| daily | `minio-backup` · `pg-backup` · `postgres-backup` · `docs-site-rebuild` · `pr-staleness-check` · `cron-freshness-check` · `port-pr-reconcile` | 26h |
| weekly (Sun) | `sonar-scan` · `code-scan-suite` | 8d |

**Budgets are per-cadence deliberately.** A blanket "no success in 24h" would false-fire on both
weekly jobs every single week, and a permanently-lit alert is worse than no alert — which is exactly
what `WeylandErrorLogSpike` was found doing on 2026-08-22, matching `NOERROR` with `/error/`.

`cron-freshness-check` **watches itself** in the daily row. It is the job that detects stopped
scheduled work, so its own silent failure would reopen the blind spot the rule exists to close.

A separate `ScheduledJobNeverSucceeded` rule uses `absent()`: a CronJob that has never succeeded
exports **no series at all**, so every threshold rule is silent for it — `time() - <nothing> > budget`
matches nothing and alerts on nothing.

### Freshness is only half — the failure side (B140, 2026-08-24)

Everything above answers **"did it stop?"**. A job that **ran and broke** and then succeeded inside its
budget is invisible to all of it, because one later success advances `last_successful_time` and the
rule goes quiet. `dagster-freshness-check-29791170` sat `Failed` for **19 hours** exactly that way; by
the time anyone noticed, the pod and its events had aged out and the cause was unrecoverable.

Two rules close it, and the split is deliberate:

| Rule | Covers | Severity |
|---|---|---|
| `ScheduledBackupFailed` | `minio-backup` · `pg-backup` · `postgres-backup` | **critical** — these losing a run costs DATA, not freshness |
| `ScheduledJobFailed` | the other seven | warning |

**Neither carries a namespace selector, deliberately.** The 10 CronJobs span `weyland`, `data-mesh`
and `minio`, and a namespace selector is precisely the bug being corrected: the estate's previous
only failure rule, `DataMeshBackupFailed`, read as `job_name=~"(minio|pg)-backup.*"` — both backups —
while `namespace="data-mesh"` one line above silently excluded `minio-backup`, which lives in ns
`minio`. **A failing MinIO backup, protecting the irreplaceable `mlflow` and `tofu-state` buckets,
alerted nobody.** A label selector and a name regex disagreeing is invisible unless you check where
the objects actually live.

The `-[0-9]+` suffix matches how kube-state-metrics names a CronJob-spawned Job
(`<cronjob>-<unix-minutes>`), which also keeps hand-launched ad-hoc Jobs (`scan-suite-adhoc`) out.

The guard asserts **exactly one** failure rule per CronJob — zero is a blind spot, two is a double
page, and duplicate pages are how an on-call learns to ignore a rule.

### The budgets are guarded, not trusted

`scripts/check-cron-freshness-budgets.sh` (CI `repo-guards`) asserts the three surfaces agree — the
manifest `schedule:`, this rule's budget, and the `docs/schedules.md` row. It fails if a CronJob has
**no rule** covering it, if a budget is not ≥ its period + 5% slack, if a job has **no schedules.md
row**, or if a fixed-time schedule sets **no `spec.timeZone`** (which silently runs it in UTC).

Run it directly:

```
bash scripts/check-cron-freshness-budgets.sh --list
```

`--list` prints the per-CronJob table and exits 0; without it the guard gates. It **fails closed** —
an unparseable schedule or a missing input is an error, never a skip.

## Reaping stale Port PR entities (B144)

`github-weyland` fetches **only open PRs** — confirmed in the integration's own stored raw examples
(`[Rest] Fetching open PRs`). When a PR closes it stops appearing in the source data, and an incremental
sync **upserts but never deletes**. The entity survives forever claiming `status: open`, `closedAt: null`.

The ship loop makes that a steady producer rather than a curiosity: `ship-images.sh` opens a tag-bump PR
on most runs and its FR2.3 gate closes superseded ones outright. Two were caught by hand three days apart
(weyland-lab #34 and #36) before this job existed.

**Why it matters:** these entities feed `service/dora_lead_time` and `service/delivery_performance`. A PR
that closed weeks ago but still reads `open` inflates cycle time permanently — the scorecard gets *worse*
with age instead of measuring anything.

### Two mechanisms that do NOT work — do not re-propose them

- **`POST /v1/integration/github-weyland/resync`** returns `{"ok":true}` and does nothing. No new log
  rows, no `resyncState` movement, no entity change — even with incremental sync disabled. That 200 is
  not evidence of anything.
- **`spec.appSpec.incrementalSyncEnabled: false`** is **not durable**. Set 2026-08-23 → reverted by 08-24;
  set again → `true` by 08-25. The integration is Port-hosted SaaS (`installationType: SaasOAuth2`), so it
  re-registers and pushes its own appSpec over server-side edits. Three attempts, three reversions, no
  human action in between. (Note the top-level `{"incrementalSyncEnabled": false}` PATCH is a separate
  trap: it returns HTTP 200 and is silently ignored — the flag lives under `spec.appSpec`.)

### How it fails closed

The single decision that authorises a `DELETE` is an **allow-list**:

```sh
should_reap() { case "${1:-}" in closed) return 0 ;; *) return 1 ;; esac; }
```

`[ "$1" != "open" ]` was the obvious form and it is exactly wrong — it returns true for the **empty
string**, so an unparseable response, a renamed field or a network blip would each authorise deleting a
live entity. Everything upstream fails closed the same way: a non-200 from Port or GitHub, a token
response with no `accessToken`, an entity missing its `repository` relation or `prNumber`, or a GitHub
**404** all cause that entity to be **skipped** and the run to exit non-zero. A 404 is deliberately not
read as "gone, therefore reap" — Port knows about that PR, so a 404 means the two systems disagree, and
deleting on a disagreement is the destructive guess this job must not make.

### Running it by hand

Dry run first, always. It reports what it would reap and touches nothing:

```
cd nodes/mother/lab/weyland-platform/k8s/pr-lifecycle
awk -v key="port-pr-reconcile.sh" '$0 ~ "^  " key ": \\|" {g=1;next} g && !/^    / && !/^[ \t]*$/ {g=0} g {sub(/^    /,"");print}' port-pr-reconcile.yaml > /tmp/reap.sh
set -a && . ../../tofu/port/.env && set +a && export GITHUB_TOKEN="$(gh auth token)"
PORT_REAP_DRY_RUN=1 sh /tmp/reap.sh
```

Real output, 2026-08-25:

```
fetched the open PR entity list from Port successfully
check entity 4240999487 = midi_real_book#3 github_state=open
check entity 4345412397 = weyland-lab#36 github_state=closed
  -> would reap 4345412397 (weyland-lab#36 is closed)
...
done - 8 open PR entities checked, 1 reaped
```

Drop `PORT_REAP_DRY_RUN=1` to act. In-cluster it runs from the `port-pr-reconcile-logic` ConfigMap, which
is the same text `scripts/tests/port-pr-reconcile.bats` executes — 19 tests, most of which assert that
nothing was deleted.

### Verifying it worked

Not "the job exited 0" — compare the two systems:

```
bash -c 'cd nodes/mother/lab/weyland-platform/tofu/port && set -a && . ./.env && set +a
TOK=$(curl -sS -X POST https://api.port.io/v1/auth/access_token -H "Content-Type: application/json" -d "{\"clientId\":\"$PORT_CLIENT_ID\",\"clientSecret\":\"$PORT_CLIENT_SECRET\"}" | python3 -c "import sys,json;print(json.load(sys.stdin)[\"accessToken\"])")
curl -sS https://api.port.io/v1/blueprints/githubPullRequest/entities -H "Authorization: Bearer $TOK" | python3 -c "import sys,json;print(\"port:\",len(json.load(sys.stdin)[\"entities\"]))"
for r in weyland-lab stud.io midi_real_book Algopedia ServiceTransformation emangini-tailwind-nextjs-contentlayer; do gh pr list --repo edtbl76/$r --state open --json number --jq length; done | paste -sd+ | bc'
```

The two numbers must match. First matching run was **7 = 7** on 2026-08-25, immediately after the reaper
removed weyland-lab #36.

### Secret

`port-pr-reconcile-creds` (keys `clientId` / `clientSecret`), Port **organization** credentials.
**Deliberately NOT `weyland/port-creds`** — that one is mounted by `dagster-user-code` and, as of
2026-08-25, holds the literal placeholders `YOUR_ID` / `YOUR_SECRET` and returns HTTP 401 (**B147**).
Verify a fresh copy by decoding the **stored** value and authenticating with it, never by `DATA 2`.

## Operating it

Run either job now (either host with `kubectl`; these are on **mother**):

```
kubectl -n weyland create job cron-freshness-adhoc --from=cronjob/cron-freshness-check
```

```
kubectl -n weyland create job pr-staleness-adhoc --from=cronjob/pr-staleness-check
```

Read the result — the tail line carries the counts:

```
kubectl -n weyland logs job/cron-freshness-adhoc
```

Expected tail: `done - N cron(s) checked, M alert(s) fired`. **Zero crons checked exits non-zero by
design** — a watchdog that finds nothing and reports success is emitting a green signal.

Check the cron the watchdog watches, by hand:

```
curl -s -o /tmp/cron.json -w '%{http_code}\n' -H "Authorization: Bearer $WOODPECKER_TOKEN" "$WOODPECKER_SERVER/api/repos/2/cron"
```

`enabled` must be `true` **and** `next_exec` must be in the **future**. A `next_exec` of `0` means the
cron has never been scheduled — the created-disabled state.

> Note the split `curl`: status code to stdout, body to a file. `curl -sf ... | jq` collapses every
> non-2xx to exit 0, so a 401 reaches `jq` as empty input and the run reports "no crons" —
> indistinguishable from a healthy repo that has none. That bug was in `pr-staleness-check` itself on
> its first live run.

## Secrets

| Secret | Namespace | Holds | Sealed CR |
|---|---|---|---|
| `pr-lifecycle-github` | `weyland` | GitHub PAT, `Pull requests: read` on the six active repos | `k8s/sealed-secrets/sealed/weyland__pr-lifecycle-github.yaml` |
| `cron-freshness-woodpecker` | `weyland` | Woodpecker API token (user-scoped) | `k8s/sealed-secrets/sealed/weyland__cron-freshness-woodpecker.yaml` |
| `port-pr-reconcile-creds` | `weyland` | Port **organization** clientId / clientSecret (B144) | `k8s/sealed-secrets/sealed/weyland__port-pr-reconcile-creds.yaml` |

All three are in the `SECRETS=(…)` allow-list in `scripts/seal-secrets.sh` — that array is the source of
truth for what gets sealed, and it is an **allow-list, not a filter**: anything missing from it is
silently never sealed. See [secrets.md](secrets.md) for the mechanism.

**Verify a freshly created secret before trusting it.** An empty or truncated value is accepted
silently (`DATA 1`, pod starts) and fails only at runtime:

```
kubectl -n weyland get secret cron-freshness-woodpecker -o jsonpath='{.data.token}' | wc -c
```

For a token of *n* characters that must equal `ceil(n/3)*4`.

## Istio

Both pods are **meshed** (`sidecar.istio.io/inject: "true"`), because Alertmanager and the Woodpecker
server are in-cluster. The cost is that the injected `istio-proxy` runs forever, so the Job never
reaches `Completed` on its own and `concurrencyPolicy: Forbid` would deadlock every later run. Two
things handle it: a `/quitquitquit` POST to ports 15020/15000 after the script, and
`activeDeadlineSeconds: 180` as a backstop if the sidecar refuses to exit.

## Where the logic lives

The decision logic is in a **ConfigMap**, not inline in the container args, because
`scripts/tests/pr-staleness.bats`, `scripts/tests/cron-freshness.bats` and
`scripts/tests/port-pr-reconcile.bats` extract and execute that exact text. A tested copy sitting beside a deployed copy drifts, and the drift is silent — both halves
keep passing their own checks.

```
docker run --rm -v "$PWD:/code:ro" -w /code bats/bats:latest scripts/tests/
```

Each suite's first test asserts the logic is actually extractable from the manifest. Without that
tripwire, every later test would be vacuously green against an empty file.

`port-pr-reconcile.bats` adds a second seam worth knowing about: its two **side-effecting** operations
are reached through `GH_STATE_FN` / `PORT_DELETE_FN` indirection rather than called by name. A plain PATH
stub cannot intercept them — a shell function always beats an executable of the same name, so the real
`curl` implementation would shadow the stub and the test would hit the live API while appearing to pass.

## Related

- [ship-images.md](ship-images.md) — the loop these watch
- [woodpecker.md](woodpecker.md) — the `nightly-images` cron itself
- [secrets.md](secrets.md) — sealing mechanism
- `docs/schedules.md` — both CronJobs' slots, and the off-hours rule that picked them
- `docs/arch.md` §10b — the decision matrix and the bug class behind all of this
