# B37 — AIDLC Knowledge-Base Ingestion (MinIO → RAG)

Ingest the three AIDLC knowledge repositories (`.methodaidlc/` engineering + consulting + industry, ~511
chunk-eligible markdown files) into the multi-backend RAG so `/context/*` can answer with *domain* knowledge,
not just infra docs. **On-demand** (the corpus is static) — there is no schedule; you re-run after re-uploading.

**Shape:** the source is the user's own IP, kept **out of git** and **brand-neutral**. A local scrub strips all
"Method" branding into a staging copy, which is uploaded to a **private MinIO bucket**; a Dagster asset reads the
bucket and writes to all 4 backends under an `aidlc-kb/` `source_path` namespace (so it coexists with the `docs/`
corpus in the same stores and is found by the same retrieval). Phase 1 = chunk-ingest (this runbook). Phase 2 =
frontmatter→Neo4j graph (B37 step 5). LLM concept extraction is deferred to **B38**.

---

## Pieces
- Scrub script: `nodes/mother/lab/weyland-platform/scripts/aidlc-kb-scrub.py`
- Dagster asset: `weyland_pipeline/assets/aidlc_kb.py` → `aidlc_kb_ingest` (group `aidlc_kb`)
- Job: `weyland_aidlc_kb_job` (on-demand; subtracted from the 15-min `weyland_ingestion_job`)
- MinIO bucket: `aidlc-kb` (private), endpoint `minio.minio.svc.cluster.local:9000` in-cluster / `s3.weyland.lab` via `mc`
- Secret: `aidlc-kb-minio-secret` in ns `weyland` (mirrors the `minio` ns creds — secretKeyRef can't cross ns)

---

## Re-ingest (the normal on-demand flow)

**1. Scrub to a brand-neutral staging copy** (local, on rogueone). Verifies 0 brand "Method" survives while
keeping technical terms (`Template Method`, `Factory Method`, …):
```
python3 nodes/mother/lab/weyland-platform/scripts/aidlc-kb-scrub.py --src .methodaidlc --dest /tmp/aidlc-kb-staging
```

**2. Upload to MinIO** (`mc` alias `weyland` → `s3.weyland.lab`; mirror = upsert + delete removed):
```
mc mirror --overwrite --remove /tmp/aidlc-kb-staging/ weyland/aidlc-kb/
```
```
mc ls --recursive weyland/aidlc-kb/ | wc -l
```

**3. Trigger** at `dagster.weyland.lab` → Jobs → `weyland_aidlc_kb_job` → Materialize all.
(Or check the asset `aidlc_kb_ingest` in the Asset graph.)

**4. Verify** (see below).

> **Hash-gate:** unchanged files are skipped (compared to `rag_documents.content_hash`), so re-runs are cheap
> no-ops. Only changed/added/removed files do work. The **first** full run takes ~1h (a few thousand chunks ×
> Weaviate's per-chunk insert + 2 cross-ref calls, each through the Istio sidecar) — that cost is one-time.

---

## First-time / after-code-change setup

**Mint the MinIO secret** in the Dagster namespace (creds = the lab dev creds; never commit):
```
kubectl create secret generic aidlc-kb-minio-secret -n weyland --from-literal=access_key=admin --from-literal=secret_key=weyland_dev_password
```

**Rebuild + redeploy the user-code image** (the asset needs the `minio` dep + MinIO env in `user-code.yaml`).
Copy changed source to mother by explicit path (rsync into an existing dir leaves stale files unless you use `--delete`), then on mother in
`~/lab/weyland-platform/services/weyland-dagster`:
```
docker build -t weyland-dagster-user-code:local .
```
```
docker save weyland-dagster-user-code:local | sudo k3s ctr images import -
```
```
kubectl apply -f ~/lab/weyland-platform/k8s/dagster/user-code.yaml && kubectl rollout restart deploy/dagster-user-code -n weyland
```

---

## Verify

**Counts in pgvector** (expect ~511 docs, a few thousand chunks):
```
kubectl exec -n weyland deploy/weyland-postgres -- psql -U weyland -d weyland -c "SELECT count(*) FROM rag_documents WHERE source_path LIKE 'aidlc-kb/%';"
```

**Retrieval — confirm KB content is actually answerable.** NOTE: `/context/search` and `/context/ask` are
**POST** (a GET returns `{"detail":"Method Not Allowed"}`). The full RAG answer (calls Ollama — slow on CPU,
give it a minute):
```
curl -s -X POST http://mother:30080/context/ask -H 'Content-Type: application/json' -d '{"query":"what is domain-driven design","backend":"pgvector"}'
```
A correct result cites AIDLC KB files in `sources`, e.g. `domain-driven-design.md` / `context-mapping.md`.

**Retrieval-only** (faster — no generation; body + `?backend=` query param):
```
curl -s -X POST "http://mother:30080/context/search?backend=pgvector" -H 'Content-Type: application/json' -d '{"query":"domain-driven design"}'
```

**Phase 2 — frontmatter graph (Neo4j).** Confirm the entry graph built + a real traversal (DDD should link to
its four declared neighbors). Baseline 2026-06-19: 510 entries, 2311 RELATED_TO edges, 10 stages.
```
kubectl exec -n weyland deploy/neo4j -- cypher-shell -u neo4j -p "$(kubectl get secret neo4j-secret -n weyland -o jsonpath='{.data.password}' | base64 -d)" "MATCH (e:Entry {domain:'aidlc-kb'}) RETURN count(e) AS entries; MATCH (:Entry)-[r:RELATED_TO]->(:Entry) RETURN count(r) AS related_edges; MATCH (e:Entry {entry_id:'domain-driven-design'})-[:RELATED_TO]->(b) RETURN b.entry_id;"
```
The graph rebuilds when content changes OR when no `:Entry` graph exists yet; a pure no-op run with a present
graph skips it. Edge model: `(:Entry)-[:RELATED_TO]->(:Entry)`, `-[:SURFACES_AT]->(:Stage)`,
`-[:TAGGED]->(:Tag)`, `-[:IN_VERTICAL]->(:Vertical)` — all from declared frontmatter, no LLM (that's B38).

---

## Graph algorithms (GDS)

The Neo4j **Graph Data Science** plugin is enabled (`NEO4J_PLUGINS=["apoc","graph-data-science"]` in
`k8s/neo4j.yaml` — free Community edition, auto-downloaded by the `neo4j:5` image; `RETURN gds.version()`
confirms). It runs in-memory algorithms over the frontmatter `:Entry` graph. Set `PW` first
(`PW=$(kubectl get secret neo4j-secret -n weyland -o jsonpath='{.data.password}' | base64 -d)`), then:

Project the graph (undirected `RELATED_TO`); re-runnable (drops first):
```
kubectl exec -n weyland deploy/neo4j -- cypher-shell -u neo4j -p "$PW" "CALL gds.graph.drop('aidlc', false) YIELD graphName; CALL gds.graph.project('aidlc','Entry',{RELATED_TO:{orientation:'UNDIRECTED'}}) YIELD nodeCount, relationshipCount RETURN nodeCount, relationshipCount;"
```
PageRank — the load-bearing concepts:
```
kubectl exec -n weyland deploy/neo4j -- cypher-shell -u neo4j -p "$PW" "CALL gds.pageRank.stream('aidlc') YIELD nodeId, score RETURN gds.util.asNode(nodeId).entry_id AS entry, round(score,3) AS pagerank ORDER BY pagerank DESC LIMIT 12;"
```
Louvain — auto-clustered themes:
```
kubectl exec -n weyland deploy/neo4j -- cypher-shell -u neo4j -p "$PW" "CALL gds.louvain.stream('aidlc') YIELD nodeId, communityId RETURN communityId, count(*) AS size, collect(gds.util.asNode(nodeId).entry_id)[..6] AS sample ORDER BY size DESC LIMIT 8;"
```
**Baseline 2026-06-19** (510 nodes / 4622 undirected rels): PageRank top = event-driven-architecture, ci-cd,
microservices, rest-constraints, caching-strategies, domain-driven-design, infrastructure-as-code,
team-topologies, circuit-breaker. Louvain ≈ 8 communities (design patterns 85, AI/ML 67, security/ops 64,
strategy/consulting 46, async/concurrency 45, observability 45, discovery/research 42, frontend 30).

**Known wrinkle:** `entry_id` is unique *per repo* but collides *across* the three (e.g. `wardley-mapping`,
`team-topologies` appear in two) → duplicate `:Entry` nodes, visible as repeated PageRank rows. Harmless for
now; if it matters, key entries by `(entry_id, repo)` or dedupe in the graph step.

## Visual exploration

**NeoDash** — the chosen dashboard/viz tool — is deployed at **`http://mother:30088`** (`k8s/neodash.yaml`,
free + works with Community). It's a browser-side app: served over plain HTTP (matching Neo4j's HTTP/Bolt
NodePorts) so the browser can talk to the plaintext Bolt port without a mixed-content block. Connect it to
`neo4j://192.168.1.243:30086`, database `neo4j`, user `neo4j`, dev password. Then build graph/table/chart
reports with Cypher (e.g. `MATCH (e:Entry {entry_id:'domain-driven-design'})-[:RELATED_TO]->(b) RETURN e,b`).

Also free: **Neo4j Browser** (`http://mother:30085`) renders the graph from Cypher. **Bloom** (search-driven
explorer) needs Enterprise/Aura — *not* free here; the only homelab route was Neo4j Desktop on rogueone under
a dev license, parked in favor of NeoDash.

## Notes / gotchas
- **Prune isolation:** the KB and `docs/` share the same stores. The 4 docs-pipeline writes are scope-guarded to
  skip `aidlc-kb/` (pgvector `NOT LIKE`, neo4j `STARTS WITH`, weaviate prefix-filter, qdrant `domain="aidlc-kb"`
  payload exclusion), and `aidlc_kb_ingest` only prunes within `aidlc-kb/`. So neither corpus wipes the other.
- **Empty-read safety:** if the MinIO read returns 0 objects (bucket/creds problem), the asset writes nothing AND
  skips its prune — it will not wipe an existing KB on a bad run.
- **Not chunked:** `index.md` and `README.md` are skipped (navigation/brand). `index.md` may feed the Phase-2
  frontmatter graph.
- **Brand scrub** runs on a *staging copy only* — never the live `.methodaidlc/` source, which intentionally
  references "Method" to drive the AIDLC workflow.
