from dagster import asset
from weyland_pipeline.resources import PostgresResource


@asset(description="Per-file compare of incoming hash vs stored hash. Returns a per-source_path changed map.")
def hash_check(
    source_document: list[dict],
    content_hash: dict,
    postgres: PostgresResource,
) -> dict:
    # Result keyed by source_path:
    #   {source_path: {"changed": bool, "stored_hash": str | None, "incoming_hash": str}}
    # Per BR-01, per file: no row -> changed; hash differs -> changed; hash matches -> unchanged.
    result: dict = {}

    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            for doc in source_document:
                source_path = doc["source_path"]
                incoming_hash = content_hash[source_path]

                cur.execute(
                    "SELECT content_hash FROM rag_documents WHERE source_path = %s",
                    (source_path,),
                )
                row = cur.fetchone()

                if row is None:
                    result[source_path] = {
                        "changed": True,
                        "stored_hash": None,
                        "incoming_hash": incoming_hash,
                    }
                else:
                    stored_hash = row[0]
                    result[source_path] = {
                        "changed": stored_hash != incoming_hash,
                        "stored_hash": stored_hash,
                        "incoming_hash": incoming_hash,
                    }

    return result
