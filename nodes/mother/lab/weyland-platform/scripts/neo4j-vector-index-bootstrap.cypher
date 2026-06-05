// One-time bootstrap: create vector index on Chunk.embedding for similarity search.
// Run before U4 Build and Test. Safe to re-run (IF NOT EXISTS).
//
// From mother:
//   kubectl exec -n weyland deploy/neo4j -- cypher-shell -u neo4j -p <password> < neo4j-vector-index-bootstrap.cypher
//
// Or interactively via Neo4j Browser at http://mother:30085

CREATE VECTOR INDEX weyland_chunk_embedding IF NOT EXISTS
FOR (c:Chunk) ON c.embedding
OPTIONS { indexConfig: { `vector.dimensions`: 384, `vector.similarity_function`: 'cosine' } };
