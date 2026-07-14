"""Qdrant handler — mirrors the retired qdrant_write asset exactly: collection `weyland_chunks`, 384-dim
cosine, deterministic point id uuid5(source_path:chunk_index), same payload shape. delete-by-source_path is
the streaming form of the asset's per-doc clear + orphan prune; it is scoped to the doc's own path, so the
aidlc-kb corpus (different source_paths, owned by a separate ingest) is never touched."""
import os
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams

COLLECTION = "weyland_chunks"
DIMS = 384
_NS = uuid.NAMESPACE_DNS


def _point_id(source_path: str, chunk_index: int) -> str:
    return str(uuid.uuid5(_NS, f"{source_path}:{chunk_index}"))


class QdrantHandler:
    def __init__(self):
        url = os.environ.get("QDRANT_URL", "http://qdrant.weyland.svc.cluster.local:6333")
        self.client = QdrantClient(url=url)

    def ensure(self):
        if not self.client.collection_exists(COLLECTION):
            self.client.create_collection(
                collection_name=COLLECTION,
                vectors_config=VectorParams(size=DIMS, distance=Distance.COSINE),
            )

    def on_delete(self, source_path: str):
        self.client.delete(
            collection_name=COLLECTION,
            points_selector=Filter(must=[FieldCondition(key="source_path", match=MatchValue(value=source_path))]),
        )

    def on_upsert(self, rec: dict):
        self.client.upsert(
            collection_name=COLLECTION,
            points=[PointStruct(
                id=_point_id(rec["source_path"], rec["chunk_index"]),
                vector=rec["vector"],
                payload={
                    "source_path": rec["source_path"],
                    "source_name": rec.get("source_name"),
                    "chunk_index": rec["chunk_index"],
                    "chunk_title": rec.get("chunk_title"),
                    "content": rec.get("chunk_text"),
                },
            )],
        )
