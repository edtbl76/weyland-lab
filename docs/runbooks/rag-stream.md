# RAG streaming indexer — runbook

How the lab's RAG index stays current: changed documents are chunked, embedded and published to Redpanda, and five
consumers write them into the five retrieval stores the tool-server searches. Design:
[design/rag-streaming-indexer-design.md](../design/rag-streaming-indexer-design.md). Flow:
[diagrams/flow-rag-stream.md](../diagrams/flow-rag-stream.md). Demo: [demos/rag-stream.md](../demos/rag-stream.md).
Written by B239 (2026-11-08), which found no runbook for operating it.

## How it is built

| Part | Where | Role |
|---|---|---|
| Producer `rag_stream_produce` | Dagster asset (group `rag`), runs inside `weyland_ingestion_job`, daily 02:17 NY | collects the repo's documents, hashes them, and for each changed one chunks it, gets embeddings, and publishes upserts; deleted docs get tombstones |
| Embedder `rag-embed` | rogueone, systemd unit, `http://192.168.1.230:8900` | `BAAI/bge-base-en-v1.5` at a pinned revision, 768 dims, CPU ([embedding-model-swap.md](embedding-model-swap.md)) |
| Topic `rag.chunks` | Redpanda (`redpanda-0`, ns `data-mesh`) | Confluent Avro, key = `source_path`, upsert or delete-tombstone |
| Consumers `rag-index-{qdrant,weaviate,opensearch}` | ns `data-mesh` (no sidecar) | one image (`weyland-rag-index`), `STORE` env picks the target |
| Consumers `rag-index-{pgvector,neo4j}` | ns `weyland` (sidecar on, Kafka ports excluded) | same image |
| Change detection `rag_manifest` | core Postgres (`source_path` PK + `content_hash`) | what was indexed, so only changes are re-sent and removed files are pruned |

Each consumer has its own consumer group (`rag-index-<store>`), so the five stores advance independently.

## Is it healthy?

All five consumers running:

```bash
kubectl -n data-mesh get deploy rag-index-qdrant rag-index-weaviate rag-index-opensearch; kubectl -n weyland get deploy rag-index-pgvector rag-index-neo4j
```

The embedder:

```bash
curl -s http://192.168.1.230:8900/health
```

Expected: `{"status":"ok","model":"BAAI/bge-base-en-v1.5","revision":"a5beb1e3…","dim":768,"device":"cpu"}`.

Consumer lag, all five groups (0 means every published chunk is indexed):

```bash
for g in qdrant weaviate opensearch pgvector neo4j; do printf '%-12s ' $g; kubectl -n data-mesh exec redpanda-0 -c redpanda -- rpk group describe rag-index-$g | awk '/^STATE/{s=$2} /TOTAL-LAG/{l=$2} END{print "state="s" lag="l}'; done
```

Expected (2026-11-08): `state=Stable lag=0` for all five.

Index size in Qdrant (the other stores hold the same chunks):

```bash
curl -s http://192.168.1.243:30083/collections/weyland_chunks | python3 -c "import json,sys; r=json.load(sys.stdin)['result']; print(r['points_count'], r['status'])"
```

Expected: about 10,500 points, `green` (10,540 on 2026-11-08).

The producer's last run is the ingestion job's; why it failed, if it did: [dagster.md § Why did a run fail?](dagster.md#why-did-a-run-fail)
with `--job weyland_ingestion_job`.

## What broke? Symptom to cause

| Symptom | Likely cause | Check and fix |
|---|---|---|
| lag on one group rising, the others 0 | that consumer is down or its store rejects writes | its pod and logs (below); the store's health on the tool-server (`/qdrant/health` …, [tool-server.md](tool-server.md)) |
| lag rising on every group | Redpanda or the schema registry is unhealthy | `kubectl -n data-mesh exec redpanda-0 -c redpanda -- rpk cluster health` ([streaming.md](streaming.md)) |
| the ingestion run fails in `rag_stream_produce` | `rag-embed` down on rogueone, or Redpanda unreachable | the embedder health above; `systemctl status rag-embed` on rogueone |
| a doc edit never shows up in answers | the producer has not run since (daily 02:17), or the change was in an excluded path | run it now (below); exclusions are in `source_document.py` |
| answers find old text from a deleted file | its tombstone was not consumed by a store | that group's lag; the consumer's logs |

## Logs

```bash
kubectl -n data-mesh logs deploy/rag-index-qdrant --tail=100
```

The same for `rag-index-weaviate` and `rag-index-opensearch` in `data-mesh`, and `rag-index-pgvector` /
`rag-index-neo4j` in `weyland` (add `-c rag-index` there if the sidecar's logs get in the way). The embedder's logs
are on rogueone:

[rogueone]
```bash
journalctl -u rag-embed --no-pager -n 100
```

## Index changes now

Launch only the producer through Dagster, so the run is recorded and counts for the watchdog. It sends only what
changed since the last run:

```bash
kubectl exec -n weyland deploy/dagster-user-code -- python3 -c "import json,urllib.request;q='mutation(\$p:ExecutionParams'+chr(33)+'){launchRun(executionParams:\$p){__typename ... on LaunchRunSuccess{run{runId}} ... on PythonError{message}}}';v={'p':{'selector':{'repositoryLocationName':'weyland_pipeline','repositoryName':'__repository__','jobName':'weyland_ingestion_job','assetSelection':[{'path':['rag_stream_produce']}]},'runConfigData':{}}};r=urllib.request.Request('http://dagster-webserver.weyland.svc.cluster.local:3000/graphql',data=json.dumps({'query':q,'variables':v}).encode(),headers={'Content-Type':'application/json'});print(json.load(urllib.request.urlopen(r))['data']['launchRun'])"
```

Then watch the lag go up and back to 0 with the lag command above. Do **not** use `dagster asset materialize` through
`kubectl exec` for this: that runs on a throwaway instance the watchdog never sees ([dagster.md § Run a job now](dagster.md#run-a-job-now)).

## Restart a consumer

```bash
kubectl -n data-mesh rollout restart deploy/rag-index-qdrant
```

(or the matching deployment and namespace). A consumer resumes from its group's committed offset, so nothing is lost
or re-sent.

## Rebuild from scratch (destructive)

Deleting the topic and the consumer groups and re-running the producer with an empty `rag_manifest` re-indexes
everything. It empties the live index while it runs. The steps are in [demos/rag-stream.md § Cleanup / teardown](../demos/rag-stream.md);
do it only with a reason, and expect retrieval to be degraded until every group's lag is back to 0.

## Related

- Search side: [tool-server.md](tool-server.md). Embedding model and its pin: [embedding-model-swap.md](embedding-model-swap.md).
  Redpanda: [streaming.md](streaming.md). Restore: the index is reproducible from the repo (`docs/dr.md`,
  reproducible stores).
