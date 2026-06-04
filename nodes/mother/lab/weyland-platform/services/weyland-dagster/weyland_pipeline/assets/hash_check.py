from dagster import asset
from weyland_pipeline.resources import PostgresResource


@asset(description="Compare incoming hash against stored hash. Returns changed=True if content is new or different.")
def hash_check(
    source_document: dict,
    content_hash: dict,
    postgres: PostgresResource,
) -> dict:
    incoming_hash = content_hash["hash"]
    source_path = source_document["source_path"]

    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            # TODO: Query rag_documents for the stored content_hash where source_path matches.
            # Set changed=True if no row exists or if the stored hash differs from incoming_hash.
            # Return {"changed": bool, "stored_hash": str | None}
            #
            # Table: rag_documents
            # Columns: source_path (text), content_hash (text)
            #
            # Constraints to enforce (per BR-01):
            #   - No row found     → changed=True,  stored_hash=None
            #   - Hash matches     → changed=False, stored_hash=<stored>
            #   - Hash differs     → changed=True,  stored_hash=<stored>

            cur.execute(
                "SELECT content_hash FROM rag_documents WHERE source_path = %s",
                (source_path,),
            )
            row = cur.fetchone()

    if row is None:
        return {"changed": True, "stored_hash": None}

    stored_hash = row[0]
    return {"changed": stored_hash != incoming_hash, "stored_hash": stored_hash}
