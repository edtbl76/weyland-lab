from dagster import asset


@asset(description="STUB — wired in U3.")
def neo4j_write(embeddings: list[dict]) -> dict:
    return {"status": "stub", "chunks_written": 0}
