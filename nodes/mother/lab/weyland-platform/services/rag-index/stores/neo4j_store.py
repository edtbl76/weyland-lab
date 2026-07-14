"""Neo4j handler — Document/Chunk graph (mirrors the retired neo4j_write asset, incl. the BELONGS_TO + NEXT
chain). Streaming form: MERGE (idempotent) per record; delete = DETACH DELETE the doc's nodes. NEXT is built
from the previous chunk, which arrives earlier on the same (source_path-keyed) partition. execute_write is the
retryable managed transaction — the atomic-retry that survives the Envoy Bolt keepalive resets. Meshed consumer
(strict Bolt), kafka ports excluded from the sidecar."""
import os

from neo4j import GraphDatabase

_UPSERT = """
MERGE (d:Document {source_path: $sp}) SET d.source_name = $sn, d.name = $sn
MERGE (c:Chunk {source_path: $sp, chunk_index: $idx})
  SET c.chunk_title = $title, c.content = $content, c.embedding = $emb
MERGE (c)-[:BELONGS_TO]->(d)
WITH c
OPTIONAL MATCH (p:Chunk {source_path: $sp, chunk_index: $prev})
FOREACH (_ IN CASE WHEN p IS NULL THEN [] ELSE [1] END | MERGE (p)-[:NEXT]->(c))
"""

_DELETE = "MATCH (n) WHERE (n:Document OR n:Chunk) AND n.source_path = $sp DETACH DELETE n"


class Neo4jHandler:
    def __init__(self):
        uri = os.environ.get("NEO4J_URI", "bolt://neo4j.weyland.svc.cluster.local:7687")
        user = os.environ.get("NEO4J_USER", "neo4j")
        self.driver = GraphDatabase.driver(uri, auth=(user, os.environ["NEO4J_PASSWORD"]))

    def ensure(self):
        pass

    def on_delete(self, source_path: str):
        with self.driver.session() as s:
            s.execute_write(lambda tx: tx.run(_DELETE, sp=source_path))

    def on_upsert(self, rec: dict):
        with self.driver.session() as s:
            s.execute_write(lambda tx: tx.run(
                _UPSERT, sp=rec["source_path"], idx=rec["chunk_index"], prev=rec["chunk_index"] - 1,
                sn=rec.get("source_name"), title=rec.get("chunk_title") or "",
                content=rec.get("chunk_text"), emb=rec["vector"]))
