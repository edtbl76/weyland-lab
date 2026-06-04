import json
from dagster import asset, Output, MetadataValue
from weyland_pipeline.resources import PostgresResource


def _to_vector(values: list[float]) -> str:
    return "[" + ",".join(str(v) for v in values) + "]"


@asset(description="Upsert document and write chunks+embeddings to pgvector. No-op if embeddings list is empty.")
def pgvector_write(
    source_document: dict,
    content_hash: dict,
    embeddings: list[dict],
    postgres: PostgresResource,
) -> Output[dict]:
    if not embeddings:
        return Output(
            {"chunks_written": 0, "skipped": True},
            metadata={"skipped_reason": MetadataValue.text("content unchanged")},
        )

    source_path = source_document["source_path"]
    source_name = source_document["source_name"]
    incoming_hash = content_hash["hash"]

    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO rag_documents (name, source_type, source_path, content_hash, metadata)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (source_path) DO UPDATE SET
                    name = EXCLUDED.name,
                    content_hash = EXCLUDED.content_hash,
                    updated_at = now()
                RETURNING id
                """,
                (source_name, "markdown", source_path, incoming_hash, json.dumps({})),
            )
            document_id = cur.fetchone()[0]

            cur.execute("DELETE FROM rag_chunks WHERE document_id = %s", (document_id,))

            for chunk in embeddings:
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

    return Output(
        {"document_id": document_id, "chunks_written": len(embeddings), "skipped": False},
        metadata={"chunks_written": MetadataValue.int(len(embeddings))},
    )
