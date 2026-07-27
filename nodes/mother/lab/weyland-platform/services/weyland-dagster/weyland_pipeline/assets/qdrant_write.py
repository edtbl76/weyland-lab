import uuid
from collections import defaultdict
from dagster import asset, Output, MetadataValue
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    MatchAny,
)
from weyland_pipeline.resources import QdrantResource

COLLECTION = "weyland_chunks"
DIMS = 768   # B74: bge-base-en-v1.5 (was 384 for bge-small)
_NS = uuid.NAMESPACE_DNS


def _point_id(source_path: str, chunk_index: int) -> str:
    return str(uuid.uuid5(_NS, f"{source_path}:{chunk_index}"))


def _group_by_source(embeddings: list[dict]) -> dict:
    grouped: dict = defaultdict(list)
    for chunk in embeddings:
        grouped[chunk["source_path"]].append(chunk)
    for source_path in grouped:
        grouped[source_path].sort(key=lambda c: c["chunk_index"])
    return grouped


@asset(description="Write each changed document's chunks+embeddings to Qdrant. Prunes orphan points whose source_path is no longer collected.")
def qdrant_write(
    source_document: list[dict],
    hash_check: dict,
    embeddings: list[dict],
    qdrant: QdrantResource,
) -> Output[dict]:
    current_paths = {doc["source_path"] for doc in source_document}

    client = qdrant.get_client()

    if not client.collection_exists(COLLECTION):
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=DIMS, distance=Distance.COSINE),
        )

    grouped = _group_by_source(embeddings)
    documents_written = 0
    points_written = 0
    points_pruned = 0

    if embeddings:
        for source_path, doc_chunks in grouped.items():
            source_name = doc_chunks[0]["source_name"]

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
                for chunk in doc_chunks
            ]

            client.upsert(collection_name=COLLECTION, points=points)
            documents_written += 1
            points_written += len(points)

    # Orphan prune: runs regardless of changes, but ONLY when sources were
    # actually collected (empty set => bad run, skip to avoid wiping the collection).
    if current_paths:
        # must_not + match_any => points whose source_path is NOT any current path.
        # Also exclude the aidlc-kb/ corpus (B37): those points carry domain="aidlc-kb" and are
        # owned by aidlc_kb_ingest's own prune — the docs run must never delete them.
        orphan_selector = Filter(
            must_not=[
                FieldCondition(key="source_path", match=MatchAny(any=list(current_paths))),
                FieldCondition(key="domain", match=MatchValue(value="aidlc-kb")),
            ]
        )
        # Count before deleting (Qdrant filter-delete doesn't report a removed count).
        points_pruned = client.count(
            collection_name=COLLECTION,
            count_filter=orphan_selector,
            exact=True,
        ).count
        if points_pruned:
            client.delete(collection_name=COLLECTION, points_selector=orphan_selector)
    else:
        print(
            "[qdrant_write] WARNING: current_paths is empty "
            "(no sources collected) — skipping orphan prune."
        )

    skipped = not embeddings and points_pruned == 0

    return Output(
        {
            "documents_written": documents_written,
            "points_written": points_written,
            "points_pruned": points_pruned,
            "skipped": skipped,
        },
        metadata={
            "documents_written": MetadataValue.int(documents_written),
            "points_written": MetadataValue.int(points_written),
            "points_pruned": MetadataValue.int(points_pruned),
        },
    )
