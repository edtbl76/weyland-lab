# Demo — ServiceMonitor coverage + the Trino blind spot (B148)

A ServiceMonitor that existed, was committed, was Argo-applied and was `kubectl get`-able for **59 days**
while producing zero metrics — and the three-plane guard that makes it impossible to repeat quietly.
**Executed + eyes-on 2026-08-26.**

- **Flow:** [diagrams/flow-servicemonitor-coverage.md](../diagrams/flow-servicemonitor-coverage.md)
- **Runbooks:** [trino.md](../runbooks/trino.md) · [observability.md](../runbooks/observability.md) · [schedules.md](../schedules.md)
- **Backlog:** B148 (Linear EMA-207)

## The point

Every affirmative check said Trino monitoring was fine:

```
kubectl -n data-mesh get servicemonitor trino -> trino 60d 
up{job="trino"} -> no data (reads as "idle")
Grafana -> empty panel (reads as "no traffic")
```

The `trino` Service had **no `metadata.labels` block at all**. A ServiceMonitor selects *Services* by
their own labels; the `spec.selector` beside it selects *pods*. Both said `app: trino`. Nothing matched,
so Prometheus never built a scrape pool, so there was no `up` series to be *missing*.

## CLI walkthrough (the test — RUN against live infra)

**1. The guard, whole-estate.** The inverse question: what is live that nothing is measuring?

```
bash scripts/check-servicemonitor-coverage.sh
```

Expected: `OK — 32 ServiceMonitor(s), every one reconciled against its workload.` (exit 0)

**2. The full inventory with verdicts** — including the two `unmanaged` rows (kube-apiserver and
kubelet: no k8s workload declares intent for them, and their active scrape is the evidence) and the
one documented `ACCEPTED` row (kube-etcd — k3s runs no etcd, so its chart-shipped monitor can never
match):

```
bash scripts/check-servicemonitor-coverage.sh --list
```

**3. The negative case — prove the guard can actually fail.** A guard never seen failing is not a
guard. This reproduces the exact trino shape (running, ready, zero targets) against fixtures:

```
cd /tmp && printf '[{"ns":"data-mesh","name":"trino","intended":1,"actual":1}]' > sm.json && printf '{"data":{"activeTargets":[]}}' > t.json && SM_SNAPSHOT_JSON=/tmp/sm.json TARGETS_JSON=/tmp/t.json bash ~/IdeaProjects/weyland/scripts/check-servicemonitor-coverage.sh; echo "EXIT=$?"
```

Expected: `data-mesh/trino blind intended=1 actual=1 targets=0` and **`EXIT=1`**.
Exit **1** = the estate has a defect; exit **2** = the guard could not do its job. Conflating them
means a broken guard reads exactly like a broken cluster.

**4. Trino really is scraped now** — series, not just `up`:

```
kubectl get --raw "/api/v1/namespaces/monitoring/pods/prometheus-monitoring-kube-prometheus-prometheus-0:9090/proxy/api/v1/query?query=count(%7B__name__%3D~%22trino_.%2B%22%7D)"
```

Expected: `4228`. And `up{job="trino"}` → `1`, `scrape_samples_scraped{job="trino"}` → ~6721.

**5. The endpoint contract** — the part that was misread for 59 days. An empty password is **required**,
not missing:

```
kubectl -n data-mesh exec deploy/trino -c trino -- sh -c 'echo "with password:"; curl -s -u metrics:x http://localhost:8080/metrics | head -c 60; echo; echo "with EMPTY password:"; curl -s -o /tmp/m -w "HTTP=%{http_code} series=" -u "metrics:" http://localhost:8080/metrics; grep -c "^trino_" /tmp/m'
```

Expected: `Password not allowed for insecure authentication` then `HTTP=200 series=4228`.

**6. The test suite** — 30 cases, the decision matrix and both transports:

```
docker run --rm --entrypoint sh -v "$PWD":/w -w /w bats/bats:latest -c "apk add --no-cache python3 >/dev/null 2>&1; bats scripts/tests/servicemonitor-coverage.bats"
```

Expected: `30 tests, 0 failures`. Includes the drift case asserting the CronJob's embedded copy is
byte-identical to the repo script, and a regression case reproducing the unlabelled Service.

**7. The CronJob, on demand** (do not wait for 02:45 — validate now):

```
kubectl -n monitoring create job --from=cronjob/servicemonitor-coverage smc-adhoc-$(date +%s) && sleep 60 && kubectl -n monitoring logs -l job-name --tail=40 --prefix | tail -40
```

Expected: the `--list` inventory then `OK — 32 ServiceMonitor(s)`, and the Job reaching `Complete`
(it runs unmeshed, so no `/quitquitquit` dance is needed).

## UI walkthrough (eyes-on)

1. **Grafana → Dashboards → Trino** (`https://grafana.weyland.lab`, uid `trino-b148`).
   **UAT — confirm:**
   - **Scrape health** reads **UP**, not `NO TARGET`. That panel is the 59-day failure's tell: an empty
     stat and an idle cluster look identical everywhere else on the page.
   - **Active nodes** = 1 (single combined coordinator/worker in this lab).
   - **Cluster memory** renders a real line at ~3.0 GB pool — not "No data".
   - **Query throughput (5m)** is present; flat at zero when idle is correct. Run any query from
     Superset or DataGrip and watch `started`/`completed` move.
2. **Prometheus → Status → Targets** — `serviceMonitor/data-mesh/trino/0` is present and **UP**.
   Before the fix this pool did not exist at all, which is why it could not be found by looking for
   something broken.

## Teardown

Steps 1, 2, 4, 5, 6 are read-only. Step 3 writes two fixtures under `/tmp` (`rm /tmp/sm.json /tmp/t.json`).
Step 7 creates an ad-hoc Job — remove it with
`kubectl -n monitoring delete job -l job-name --field-selector status.successful=1` or leave it to the
`successfulJobsHistoryLimit: 3` rotation. Nothing in the demo mutates the catalog or any secret.
