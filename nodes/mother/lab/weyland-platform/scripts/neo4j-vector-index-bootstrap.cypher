// (Re)create the vector index on Chunk.embedding for similarity search — the tool-server's and the agent's `neo4j`
// retrieval backend (`db.index.vector.queryNodes('weyland_chunk_embedding', ...)`).
//
// The dimensions MUST equal the embedder's output: bge-base-en-v1.5 = 768 (B74, 2026-07-28; the tool-server's
// EMBED_DIM). A vector index of another size does not hold the chunks at all, and every query fails with
// "Index query vector has 768 dimensions, but indexed vectors have 384" — which is what happened from B74 until
// 2026-11-12 (B38): this file still said 384 and the index was never rebuilt. On an embedding-model swap, change the
// number here and re-run it (runbooks/embedding-model-swap.md lists this as a surface).
//
// It DROPS and recreates, so it is safe to re-run and always leaves the size above; the index then repopulates from
// the existing Chunk.embedding properties (no re-embedding). Run (password from the pod's own NEO4J_AUTH):
//   kubectl -n weyland exec -i deploy/neo4j -- sh -c 'cypher-shell -u neo4j -p "${NEO4J_AUTH#neo4j/}"' < nodes/mother/lab/weyland-platform/scripts/neo4j-vector-index-bootstrap.cypher
// Then wait for state ONLINE, populationPercent 100 (runbooks/neo4j.md § Vector index).

DROP INDEX weyland_chunk_embedding IF EXISTS;

CREATE VECTOR INDEX weyland_chunk_embedding IF NOT EXISTS
FOR (c:Chunk) ON c.embedding
OPTIONS { indexConfig: { `vector.dimensions`: 768, `vector.similarity_function`: 'cosine' } };
