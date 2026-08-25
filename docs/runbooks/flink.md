# Runbook — Flink streaming-processing tier (B83)

Operational guide for the Flink tier: the `weyland-flink` session cluster + the four jobs. Demo:
[../demos/flink.md](../demos/flink.md). Flow: [../diagrams/flow-flink.md](../diagrams/flow-flink.md). Design:
[../../aidlc-docs/construction/flink-streaming-design.md](../../aidlc-docs/construction/flink-streaming-design.md).

All `kubectl` runs on **mother** (`emangini@mother`). Images build on mother and `ctr import` into k3s (single
node) — never `docker pull` (`imagePullPolicy: Never`).

## Components (ns `data-mesh`)

| Component | What | Manifest |
|-----------|------|----------|
| Flink operator | watches `data-mesh`, reconciles FlinkDeployments/SessionJobs | `k8s/flink/flink-operator-values.yaml` (Argo helm) |
| `weyland-flink` | session cluster (JM+TM), image `weyland-flink:local` | `k8s/data-mesh/flink-session.yaml` |
| `flink-jars` | nginx, serves `sql-runner.jar` + `health-job.jar` for session jobs | `k8s/data-mesh/flink-jar-server.yaml` |
| `flink-history` | standalone History Server, `flink-history.weyland.lab` | `k8s/data-mesh/flink-history-server.yaml` |
| RTA / CDC / health jobs | `FlinkSessionJob`s on the session cluster | `k8s/data-mesh/flink-{rta,cdc,health}-sessionjob.yaml` |
| PyFlink job | application-mode `FlinkDeployment`, image `weyland-flink-py:local` | `k8s/data-mesh/flink-pyflink.yaml` |
| metrics | Prometheus reporter `:9249` + `ServiceMonitor` | `k8s/data-mesh/flink-metrics.yaml` |

## Build + deploy the images

Two images. Build context is `k8s/flink/` (rsynced to `~/flink-src/` on mother).

**Session image** `weyland-flink:local` (Flink + Iceberg/Nessie/Kafka jars + `sql-runner.jar` + `health-job.jar`):

```
[workstation] rsync -a --delete <repo>/k8s/flink/ emangini@mother:~/flink-src/
[mother] cd ~/flink-src && sudo docker build -t weyland-flink:local . && sudo docker save weyland-flink:local | sudo k3s ctr -n k8s.io images import -
[mother] kubectl -n data-mesh rollout restart deploy/flink-jars && kubectl -n data-mesh rollout status deploy/flink-jars   # refresh served jars
```

**PyFlink image** `weyland-flink-py:local` (Flink + python3 + `apache-flink` + Kafka/Avro jars + `music_tier.py`):

```
[mother] cd ~/flink-src && sudo docker build -f Dockerfile.pyflink -t weyland-flink-py:local . && sudo docker save weyland-flink-py:local | sudo k3s ctr -n k8s.io images import -
```

After rebuilding a jar that the session jobs fetch, `rollout restart deploy/flink-jars` so its initContainer
re-copies the new jar, then delete+re-apply the affected `FlinkSessionJob` (a bare re-apply may keep the failed
reconcile).

## Submit / manage jobs

```
[mother] kubectl -n data-mesh get flinkdeployment
[mother] kubectl -n data-mesh get flinksessionjob
[mother] kubectl apply -f ~/flink-<job>-sessionjob.yaml            # rta / cdc / health
[mother] kubectl apply -f ~/flink-pyflink.yaml                     # pyflink (app mode)
[mother] kubectl -n data-mesh delete flinksessionjob <name>        # stop a session job
[mother] kubectl -n data-mesh delete flinkdeployment flink-pyflink # tear down the bounded pyflink job
```

Job status (session job): `kubectl -n data-mesh get flinksessionjob <name> -o jsonpath='{.status.jobStatus.state}'`.
App-mode: `... get flinkdeployment flink-pyflink -o jsonpath='{.status.jobManagerDeploymentStatus} {.status.jobStatus.state}'`.

Per-vertex record counts (bisects "no output" — did the SOURCE read, or did the SINK write?):

```
[mother] JID=$(kubectl -n data-mesh exec deploy/weyland-flink -- curl -s localhost:8081/jobs | python3 -c "import sys,json;print(json.load(sys.stdin)['jobs'][0]['id'])")
[mother] kubectl -n data-mesh exec deploy/weyland-flink -- curl -s localhost:8081/jobs/$JID | python3 -c "import sys,json;d=json.load(sys.stdin);[print(v['name'][:45],'sent=',v['metrics']['write-records'],'recv=',v['metrics']['read-records']) for v in d['vertices']]"
```

### Retired: `rta-trending` (B141, manifest deleted 2026-08-24)

A **bounded** job, and its manifest is no longer in the repo. Kept here because deleting a CR should not
delete the knowledge of how the job ran.

It read the lastfm topic to the end (`scan.bounded.mode=latest-offset`), closed its tumbling windows,
wrote **5,017,946 rows across 223 snapshots** into `analytics.trending_artists` (last commit
`2026-08-21T21:50:56Z`), and **FINISHED**. Terminal state confirmed `FINISHED`, jobId
`f5920627ed8edd6701f898e5a40e4510`. The run is archived to `s3://warehouse/_flink/completed-jobs`, so
the History Server still shows it and the output data is untouched.

**Why the manifest was deleted.** A `FlinkSessionJob` CR describes a job the Operator expects to be
running. This one had legitimately ended, so the Operator reconciled it forever and emitted
`Missing / Job Not Found` as a permanent Warning. That is not an outage, but a Warning that is always
present is how a team learns to skim past Warnings that are not. A scheduled re-run would have been the
wrong shape: this was a one-shot showcase, and the continuous flagship is the CDC job.

To run it again, re-apply this (it was `k8s/data-mesh/flink-rta-sessionjob.yaml`), and **delete the CR
once `state=FINISHED`**:

```yaml
apiVersion: flink.apache.org/v1beta1
kind: FlinkSessionJob
metadata:
  name: rta-trending
  namespace: data-mesh
spec:
  deploymentName: weyland-flink       # must match the FlinkDeployment (the session cluster)
  job:
    jarURI: http://flink-jars.data-mesh.svc.cluster.local/sql-runner.jar   # operator fetches it; local:// is not fetchable for session jobs
    entryClass: lab.weyland.flink.SqlRunner
    args:
      - /opt/flink/sql/rta_trending.sql
    parallelism: 1
    upgradeMode: stateless            # bounded, no state to carry across upgrades
```

The SQL it runs is still in the repo at `k8s/flink/sql/rta_trending.sql`; only the CR was removed.

## Observability

- **UI:** `flink.weyland.lab` (JM). Per job: Overview / Checkpoints / BackPressure / **FlameGraph**
  (`rest.flamegraph.enabled`). JM/TM **Profiler** tab (async-profiler, `rest.profiling.enabled`).
- **History Server:** `flink-history.weyland.lab` — archived jobs at **`/jobs/overview`** (root `/overview` 404s).
  Archives to `s3://warehouse/_flink/completed-jobs`.
- **Metrics:** Prometheus reporter on `:9249`, scraped by the `weyland-flink` `ServiceMonitor` →
  `flink_jobmanager_*` / `flink_taskmanager_*`.

## Troubleshooting (session-earned gotchas)

- **`FlinkSessionJob` reconcile fails / jar not found** — a session-mode jarURI must be **http/s3**
  (`http://flink-jars.data-mesh.svc.cluster.local/<jar>`), never `local://` (that only works in application mode;
  the operator uploads the jar to the running cluster). If a jar 404s, `rollout restart deploy/flink-jars`.
- **Java job `NoSuchMethodError` on `ConfluentRegistryAvroDeserializationSchema.forGeneric`** — the dist ships
  `flink-sql-avro-confluent-registry` (Avro shaded) in `/opt/flink/lib`, and Flink loads `org.apache.flink.*`
  **parent-first**, so it shadows a DataStream job's bundled `flink-avro-confluent-registry` (unshaded Avro). Fix:
  **relocate** `org.apache.flink.formats.avro` to a private package in the fat jar (see `health-job/pom.xml` shade
  config). Do NOT relocate `org.apache.avro` (dist has no plain Avro on its parent classpath).
- **Job runs, source reads N, but output topic empty** — every record dropped in the operator, usually an Avro
  **field-name mismatch** (case-sensitive!). Reader field with a `default` silently resolves to null when the
  writer name differs. Dump the writer schema:
  `kubectl -n data-mesh exec redpanda-0 -- curl -s localhost:8081/subjects/<topic>-value/versions/latest`. brfss
  capitalizes (`Locationdesc`, `Data_value`); lastfm is lowercase (`artist_name`, `play_count`).
- **KafkaSink output appears in bursts, not continuously** — `AT_LEAST_ONCE` flushes on **checkpoint** (~1 min
  here). Pre-create the output topic; the sink only auto-creates on its first metadata request.
- **Source 100% idle / 0 records with data present** — check the TM log for `Seeking to earliest` /
  `Resetting offset`: `kubectl -n data-mesh logs $(kubectl -n data-mesh get pods -o name | grep taskmanager | head -1) --tail=250 | grep -iE 'offset|assigned|partition'`.
- **`rpk topic consume --num 0` hangs forever** — an empty/zero count makes rpk **tail**. Always gate:
  `[ "$HW" -gt 0 ] && rpk ... --num "$HW"`.
- **PyFlink app-mode `RECONCILING` for a while** — the `weyland-flink-py` image is ~1 GB + the python worker is
  slower to start than the Java jobs. Give it 40–60 s before checking `job=FINISHED`.
- **Retention drained a bounded source** (non-zero `LOG-START-OFFSET`) — re-produce via the Dagster
  `datasets_<domain>_stream_produce` asset before re-submitting.
