import json
from collections import defaultdict
from dagster import asset, Output, MetadataValue
from weyland_pipeline.resources import PostgresResource


def _to_vector(values: list[float]) -> str:
    return "[" + ",".join(str(v) for v in values) + "]"


def _group_by_source(embeddings: list[dict]) -> dict:
    grouped: dict = defaultdict(list)
    for chunk in embeddings:
        grouped[chunk["source_path"]].append(chunk)
    for source_path in grouped:
        grouped[source_path].sort(key=lambda c: c["chunk_index"])
    return grouped


@asset(description="Upsert each changed document and write its chunks+embeddings to pgvector. No-op if nothing changed.")
def pgvector_write(
    source_document: list[dict],
    hash_check: dict,
    embeddings: list[dict],
    postgres: PostgresResource,
) -> Output[dict]:
    if not embeddings:
        return Output(
            {"documents_written": 0, "chunks_written": 0, "skipped": True},
            metadata={"skipped_reason": MetadataValue.text("no changed content")},
        )

    meta_by_path = {doc["source_path"]: doc for doc in source_document}
    grouped = _group_by_source(embeddings)

    documents_written = 0
    chunks_written = 0

    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            for source_path, doc_chunks in grouped.items():
                meta = meta_by_path[source_path]
                source_name = meta["source_name"]
                source_type = meta["kind"]  # "markdown" | "code"
                incoming_hash = hash_check[source_path]["incoming_hash"]

                cur.execute(
                    """
                    INSERT INTO rag_documents (name, source_type, source_path, content_hash, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (source_path) DO UPDATE SET
                        name = EXCLUDED.name,
                        source_type = EXCLUDED.source_type,
                        content_hash = EXCLUDED.content_hash,
                        updated_at = now()
                    RETURNING id
                    """,
                    (source_name, source_type, source_path, incoming_hash, json.dumps({})),
                )
                document_id = cur.fetchone()[0]

                cur.execute("DELETE FROM rag_chunks WHERE document_id = %s", (document_id,))

                for chunk in doc_chunks:
                    metadata = {"title": chunk["chunk_title"]} if chunk["chunk_title"] else {}
                    cur.execute(
                        """
                        INSERT INTO rag_chunks (document_id, chunk_index, content, embedding, metadata)
                        VALUES (%s, %s, %s, %s::vector, %s)
                        """,
                        (
                            document_id,
                            chunk["chunk_index"],
                            chunk["content"],
                            _to_vector(chunk["embedding"]),
                            json.dumps(metadata),
                        ),
                    )

                documents_written += 1
                chunks_written += len(doc_chunks)

    return Output(
        {"documents_written": documents_written, "chunks_written": chunks_written, "skipped": False},
        metadata={
            "documents_written": MetadataValue.int(documents_written),
            "chunks_written": MetadataValue.int(chunks_written),
        },
    )
