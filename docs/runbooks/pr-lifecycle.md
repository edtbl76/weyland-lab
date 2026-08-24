# pr-lifecycle — the delivery-pipeline watchdogs

Two CronJobs share the `pr-lifecycle` Argo app (`k8s/pr-lifecycle/`). Neither deploys anything; both
answer the same question about the ship loop: **did the thing that was supposed to happen, happen?**

| CronJob | Schedule (NY) | Asks | Alert |
|---|---|---|---|
| `pr-staleness-check` | 05:45 daily | is a PR sitting open past its age budget? | `OpenPullRequestStale` (warning) |
| `cron-freshness-check` | 04:30 daily | is the Woodpecker `nightly-images` cron enabled, with a future `next_exec`? | `ScheduledWorkNotRunning` (critical) |

Both POST a synthetic alert to the **Alertmanager v2 API**, which needs no routing change — the
top-level route is a catch-all to `telegram`.

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
| daily | `minio-backup` · `pg-backup` · `postgres-backup` · `docs-site-rebuild` · `pr-staleness-check` · `cron-freshness-check` | 26h |
| weekly (Sun) | `sonar-scan` · `code-scan-suite` | 8d |

**Budgets are per-cadence deliberately.** A blanket "no success in 24h" would false-fire on both
weekly jobs every single week, and a permanently-lit alert is worse than no alert — which is exactly
what `WeylandErrorLogSpike` was found doing on 2026-08-22, matching `NOERROR` with `/error/`.

`cron-freshness-check` **watches itself** in the daily row. It is the job that detects stopped
scheduled work, so its own silent failure would reopen the blind spot the rule exists to close.

A separate `ScheduledJobNeverSucceeded` rule uses `absent()`: a CronJob that has never succeeded
exports **no series at all**, so every threshold rule is silent for it — `time() - <nothing> > budget`
matches nothing and alerts on nothing.

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

Both are in the `SECRETS=(…)` allow-list in `scripts/seal-secrets.sh` — that array is the source of
truth for what gets sealed. See [secrets.md](secrets.md) for the mechanism.

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
`scripts/tests/pr-staleness.bats` and `scripts/tests/cron-freshness.bats` extract and execute that
exact text. A tested copy sitting beside a deployed copy drifts, and the drift is silent — both halves
keep passing their own checks.

```
docker run --rm -v "$PWD:/code:ro" -w /code bats/bats:latest scripts/tests/
```

Each suite's first test asserts the logic is actually extractable from the manifest. Without that
tripwire, every later test would be vacuously green against an empty file.

## Related

- [ship-images.md](ship-images.md) — the loop these watch
- [woodpecker.md](woodpecker.md) — the `nightly-images` cron itself
- [secrets.md](secrets.md) — sealing mechanism
- `docs/schedules.md` — both CronJobs' slots, and the off-hours rule that picked them
- `docs/arch.md` §10b — the decision matrix and the bug class behind all of this
