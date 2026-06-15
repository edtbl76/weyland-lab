from collections import defaultdict
from dagster import asset, Output, MetadataValue
from weaviate.classes.config import Configure, Property, DataType, ReferenceProperty
from weaviate.classes.query import Filter
from weyland_pipeline.resources import WeaviateResource


def _bootstrap_schema(client) -> None:
    existing = {c.name for c in client.collections.list_all().values()}

    if "WeylandDocument" not in existing:
        client.collections.create(
            name="WeylandDocument",
            vectorizer_config=Configure.Vectorizer.none(),
            properties=[
                Property(name="source_path", data_type=DataType.TEXT),
                Property(name="source_name", data_type=DataType.TEXT),
                Property(name="name", data_type=DataType.TEXT),
            ],
        )

    if "WeylandChunk" not in existing:
        client.collections.create(
            name="WeylandChunk",
            vectorizer_config=Configure.Vectorizer.none(),
            properties=[
                Property(name="source_path", data_type=DataType.TEXT),
                Property(name="chunk_index", data_type=DataType.INT),
                Property(name="chunk_title", data_type=DataType.TEXT),
                Property(name="content", data_type=DataType.TEXT),
            ],
            references=[
                ReferenceProperty(name="hasDocument", target_collection="WeylandDocument"),
                ReferenceProperty(name="previousChunk", target_collection="WeylandChunk"),
                ReferenceProperty(name="nextChunk", target_collection="WeylandChunk"),
            ],
        )


def _group_by_source(embeddings: list[dict]) -> dict:
    grouped: dict = defaultdict(list)
    for chunk in embeddings:
        grouped[chunk["source_path"]].append(chunk)
    for source_path in grouped:
        grouped[source_path].sort(key=lambda c: c["chunk_index"])
    return grouped


@asset(description="Write each changed document's chunks+embeddings to Weaviate with cross-ref linking. No-op if nothing changed.")
def weaviate_write(
    source_document: list[dict],
    hash_check: dict,
    embeddings: list[dict],
    weaviate: WeaviateResource,
) -> Output[dict]:
    client = weaviate.get_client()

    try:
        _bootstrap_schema(client)

        if not embeddings:
            return Output(
                {"documents_written": 0, "objects_written": 0, "skipped": True},
                metadata={"skipped_reason": MetadataValue.text("no changed content")},
            )

        chunks_col = client.collections.get("WeylandChunk")
        docs_col = client.collections.get("WeylandDocument")
        grouped = _group_by_source(embeddings)

        documents_written = 0
        objects_written = 0
        cross_refs_total = 0

        for source_path, doc_chunks in grouped.items():
            source_name = doc_chunks[0]["source_name"]

            chunks_col.data.delete_many(
                where=Filter.by_property("source_path").equal(source_path)
            )
            docs_col.data.delete_many(
                where=Filter.by_property("source_path").equal(source_path)
            )

            doc_uuid = docs_col.data.insert(
                properties={
                    "source_path": source_path,
                    "source_name": source_name,
                    "name": source_name,
                }
            )

            chunk_uuids = []
            for chunk in doc_chunks:
                chunk_uuid = chunks_col.data.insert(
                    properties={
                        "source_path": source_path,
                        "chunk_index": chunk["chunk_index"],
                        "chunk_title": chunk["chunk_title"] or "",
                        "content": chunk["content"],
                    },
                    vector=chunk["embedding"],
                    references={"hasDocument": doc_uuid},
                )
                chunk_uuids.append(chunk_uuid)

            for i, chunk_uuid in enumerate(chunk_uuids):
                if i > 0:
                    chunks_col.data.reference_add(
                        from_uuid=chunk_uuid,
                        from_property="previousChunk",
                        to=chunk_uuids[i - 1],
                    )
                if i < len(chunk_uuids) - 1:
                    chunks_col.data.reference_add(
                        from_uuid=chunk_uuid,
                        from_property="nextChunk",
                        to=chunk_uuids[i + 1],
                    )

            documents_written += 1
            objects_written += len(chunk_uuids) + 1
            cross_refs_total += max(0, 2 * len(chunk_uuids) - 2)

        return Output(
            {
                "documents_written": documents_written,
                "objects_written": objects_written,
                "cross_refs_linked": cross_refs_total,
                "skipped": False,
            },
            metadata={
                "documents_written": MetadataValue.int(documents_written),
                "objects_written": MetadataValue.int(objects_written),
                "cross_refs_linked": MetadataValue.int(cross_refs_total),
            },
        )
    finally:
        client.close()
