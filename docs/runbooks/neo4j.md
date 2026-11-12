# Neo4j — runbook

The lab's graph store: the RAG document graph, the music dataset graph, the AI-DLC knowledge graph and the finance
graph, in one Neo4j 5 Community instance with APOC and GDS. Written by B239 (2026-11-08), which found no runbook for
operating it, only sections in the hydration and mesh docs.

## How it is built

- **Deployment** `neo4j` (ns `weyland`), manifest `k8s/neo4j.yaml`. Service `neo4j` with NodePorts **30085**
  (HTTP / Browser, 7474) and **30086** (Bolt, 7687). Heap 1G to 2G, page cache 2G, data PVC 20Gi (`local-path`).
  Deploys `Recreate` (single instance on RWO storage: two pods would contend for the store lock).
- **Meshed** (Istio). Long Bolt bulk loads half-open behind Envoy without TCP keepalive, so the `neo4j-bolt`
  DestinationRule sets keepalive (memory `neo4j-istio-bolt-longconn-stall`, [service-mesh-istio.md](service-mesh-istio.md)).
- **Writers:** `rag-index-neo4j` (the RAG `Document`/`Chunk` graph, [rag-stream.md](rag-stream.md)); the Dagster
  music and finance graph loaders ([datasets-hydration.md](datasets-hydration.md)); the AI-DLC KB ingest
  ([aidlc-kb-ingest.md](aidlc-kb-ingest.md)). **Readers:** the tool-server (`/neo4j/health`, graph retrieval),
  `neo4j-mcp` (read-only MCP for agents), NeoDash ([lab-uis.md](lab-uis.md)).
- **Credentials:** `NEO4J_AUTH` in the pod, from Secret `neo4j-secret`.

## Is it healthy?

```bash
kubectl -n weyland get deploy neo4j neo4j-mcp
```

Version, and the size of the graph (read-only, the password comes from the pod's own environment):

```bash
kubectl -n weyland exec deploy/neo4j -- sh -c 'cypher-shell -u neo4j -p "${NEO4J_AUTH#neo4j/}" --format plain "CALL dbms.components() YIELD name, versions, edition RETURN name, versions[0], edition; MATCH (n) RETURN count(n) AS nodes; MATCH ()-[r]->() RETURN count(r) AS rels;"'
```

Expected (2026-11-08): `"Neo4j Kernel", "5.26.28", "community"`, about 638,600 nodes and 14.3 million relationships.

What is in it, per label (APOC; reads the count store, cheap):

```bash
kubectl -n weyland exec deploy/neo4j -- sh -c 'cypher-shell -u neo4j -p "${NEO4J_AUTH#neo4j/}" --format plain "CALL apoc.meta.stats() YIELD labels RETURN labels;"'
```

Expected (2026-11-08): music (`User` 287,083, `Artist` 173,992, `Track` 109,727, `Clip` 35,824, `Album` 15,713,
`Genre` 164 …), RAG (`Document` 1,746, `Chunk` 10,540, which matches Qdrant's `weyland_chunks`), AI-DLC (`Entry` 510,
`Stage` 10), finance (`Company`, `Filing`, `SIC`, `Vertical`). A label that drops to 0 means its loader's last run
replaced it with nothing; check that loader's run ([dagster.md](dagster.md)).

From outside the cluster, the tool-server's view: `curl -s http://192.168.1.243:30080/neo4j/health`. Since 2026-11-12
(B38) it checks the **vector index**, not just the connection: `{"status":"ok","index_dims":768}` means the index exists,
matches the embedder (bge-base, 768) and answered a real query. `"status":"error"` names what is wrong.

### Vector index (`weyland_chunk_embedding`)

The RAG `neo4j` backend (the tool-server's and the agent's) searches `Chunk.embedding` through this index. Its size must
equal the embedder's output (768 since B74). **Check it** (read-only):

```bash
kubectl -n weyland exec deploy/neo4j -- sh -c 'cypher-shell -u neo4j -p "${NEO4J_AUTH#neo4j/}" --format plain "SHOW INDEXES YIELD name, state, populationPercent, options WHERE name = \"weyland_chunk_embedding\" RETURN name, state, populationPercent, options.indexConfig[\"vector.dimensions\"] AS dims;"'
```

Expected: `ONLINE`, `100.0`, `768`. **Rebuild it** (after an embedding-model swap, or if the size is wrong; it drops and
recreates, then repopulates from the stored vectors, no re-embedding):

```bash
cd /home/edwardmangini/IdeaProjects/weyland && kubectl -n weyland exec -i deploy/neo4j -- sh -c 'cypher-shell -u neo4j -p "${NEO4J_AUTH#neo4j/}"' < nodes/mother/lab/weyland-platform/scripts/neo4j-vector-index-bootstrap.cypher
```

Then re-run the check until it shows `ONLINE` and `100.0`. It stayed at 384 from B74 (2026-07-28) to 2026-11-12, and every
Neo4j vector query failed with `Index query vector has 768 dimensions, but indexed vectors have 384` while the old health
check (`RETURN 1`) said ok.

## What broke? Symptom to cause

| Symptom | Likely cause | Check and fix |
|---|---|---|
| a long load stalls with no error | Bolt connection half-open behind Envoy | the `neo4j-bolt` DestinationRule keepalive ([service-mesh-istio.md](service-mesh-istio.md)) |
| `OOMKilled` or slow queries during a big load | 2G heap / page cache against a large graph job | the logs; run big GDS or loads one at a time |
| `Chunk` count differs from Qdrant's `weyland_chunks` | `rag-index-neo4j` behind or failing | its consumer lag ([rag-stream.md](rag-stream.md)) |
| tool-server `/neo4j/health` not ok, pod healthy | mesh or auth between them | the tool-server logs ([tool-server.md](tool-server.md)) |

## Logs and restart

```bash
kubectl -n weyland logs deploy/neo4j --tail=200
```

```bash
kubectl -n weyland rollout restart deploy/neo4j && kubectl -n weyland rollout status deploy/neo4j --timeout=300s
```

Writers in progress fail during the restart; the RAG consumer resumes from its committed offset, and a Dagster
loader run must be launched again.

## Restore

No `dr.md` row yet (B240 covers every store). Every graph in it is rebuilt from sources: the RAG graph by the
streaming indexer, the music and finance graphs by their Dagster loaders, the AI-DLC graph by the KB ingest. A
rebuild of the music graph (~13.85M plays) is a long load, so the reproducible reason belongs in `dr.md` with that
cost stated.
