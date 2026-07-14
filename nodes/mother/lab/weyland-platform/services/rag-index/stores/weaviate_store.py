"""Weaviate handler — WeylandDocument + WeylandChunk (mirrors the retired weaviate_write asset). Streaming
simplification: keeps the essential chunk->doc `hasDocument` cross-ref; DROPS the previousChunk/nextChunk chain
(a graph adornment unused by vector retrieval — neo4j retains the full graph). Deterministic UUIDs make upsert
idempotent (exists -> replace, else insert). Sidecar-off consumer reaches the permissive-meshed weaviate over
plaintext http+grpc (same as qdrant); skip_init_checks avoids the grpc startup probe."""
import os
import uuid

import weaviate
from weaviate.classes.config import Configure, DataType, Property, ReferenceProperty
from weaviate.classes.query import Filter

_NS = uuid.NAMESPACE_DNS


def _doc_uuid(sp: str) -> str:
    return str(uuid.uuid5(_NS, sp))


def _chunk_uuid(sp: str, idx: int) -> str:
    return str(uuid.uuid5(_NS, f"{sp}:{idx}"))


class WeaviateHandler:
    def __init__(self):
        host = os.environ.get("WEAVIATE_HOST", "weaviate.weyland.svc.cluster.local")
        self.client = weaviate.connect_to_custom(
            http_host=host, http_port=int(os.environ.get("WEAVIATE_PORT", "8080")), http_secure=False,
            grpc_host=host, grpc_port=int(os.environ.get("WEAVIATE_GRPC_PORT", "50051")), grpc_secure=False,
            skip_init_checks=True,
        )

    def ensure(self):
        existing = set(self.client.collections.list_all())
        if "WeylandDocument" not in existing:
            self.client.collections.create(
                name="WeylandDocument", vectorizer_config=Configure.Vectorizer.none(),
                properties=[Property(name="source_path", data_type=DataType.TEXT),
                            Property(name="source_name", data_type=DataType.TEXT),
                            Property(name="name", data_type=DataType.TEXT)])
        if "WeylandChunk" not in existing:
            self.client.collections.create(
                name="WeylandChunk", vectorizer_config=Configure.Vectorizer.none(),
                properties=[Property(name="source_path", data_type=DataType.TEXT),
                            Property(name="chunk_index", data_type=DataType.INT),
                            Property(name="chunk_title", data_type=DataType.TEXT),
                            Property(name="content", data_type=DataType.TEXT)],
                references=[ReferenceProperty(name="hasDocument", target_collection="WeylandDocument")])
        self.docs = self.client.collections.get("WeylandDocument")
        self.chunks = self.client.collections.get("WeylandChunk")

    def on_delete(self, source_path: str):
        self.chunks.data.delete_many(where=Filter.by_property("source_path").equal(source_path))
        self.docs.data.delete_many(where=Filter.by_property("source_path").equal(source_path))

    def on_upsert(self, rec: dict):
        sp, idx = rec["source_path"], rec["chunk_index"]
        du, cu = _doc_uuid(sp), _chunk_uuid(sp, idx)
        doc_props = {"source_path": sp, "source_name": rec.get("source_name"), "name": rec.get("source_name")}
        if self.docs.data.exists(du):
            self.docs.data.replace(uuid=du, properties=doc_props)
        else:
            self.docs.data.insert(uuid=du, properties=doc_props)
        chunk_props = {"source_path": sp, "chunk_index": idx,
                       "chunk_title": rec.get("chunk_title") or "", "content": rec.get("chunk_text")}
        if self.chunks.data.exists(cu):
            self.chunks.data.replace(uuid=cu, properties=chunk_props, vector=rec["vector"],
                                     references={"hasDocument": du})
        else:
            self.chunks.data.insert(uuid=cu, properties=chunk_props, vector=rec["vector"],
                                    references={"hasDocument": du})
