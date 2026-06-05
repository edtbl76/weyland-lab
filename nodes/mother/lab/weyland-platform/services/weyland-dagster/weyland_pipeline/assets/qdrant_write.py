import uuid
from dagster import asset, Output, MetadataValue
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from weyland_pipeline.resources import QdrantResource

COLLECTION = "weyland_chunks"
DIMS = 384
_NS = uuid.NAMESPACE_DNS


def _point_id(source_path: str, chunk_index: int) -> str:
    return str(uuid.uuid5(_NS, f"{source_path}:{chunk_index}"))


@asset(description="Write chunks+embeddings to Qdrant. No-op if content unchanged.")
def qdrant_write(
    source_document: dict,
    hash_check: dict,
    embeddings: list[dict],
    qdrant: QdrantResource,
) -> Output[dict]:
    if not embeddings:
        return Output(
            {"points_written": 0, "skipped": True},
            metadata={"skipped_reason": MetadataValue.text("content unchanged")},
        )

    source_path = source_document["source_path"]
    source_name = source_document["source_name"]
    client = qdrant.get_client()

    if not client.collection_exists(COLLECTION):
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=DIMS, distance=Distance.COSINE),
        )

    client.delete(
        collection_name=COLLECTION,
        points_selector=Filter(
            must=[FieldCondition(key="source_path", match=MatchValue(value=source_path))]
        ),
    )

    points = [
        PointStruct(
            id=_point_id(source_path, chunk["chunk_index"]),
            vector=chunk["embedding"],
            payload={
                "source_path": source_path,
                "source_name": source_name,
                "chunk_index": chunk["chunk_index"],
                "chunk_title": chunk["chunk_title"],
                "content": chunk["content"],
            },
        )
        for chunk in embeddings
    ]

    client.upsert(collection_name=COLLECTION, points=points)

    return Output(
        {"points_written": len(points), "skipped": False},
        metadata={"points_written": MetadataValue.int(len(points))},
    )
