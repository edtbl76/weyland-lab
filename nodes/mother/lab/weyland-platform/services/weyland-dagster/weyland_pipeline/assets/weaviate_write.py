from dagster import asset


@asset(description="STUB — wired in U3.")
def weaviate_write(embeddings: list[dict]) -> dict:
    return {"status": "stub", "chunks_written": 0}
