from dagster import asset
from weyland_pipeline.resources import SentenceTransformerResource


@asset(description="Embed each chunk using BAAI/bge-small-en-v1.5. Returns empty list if chunks is empty.")
def embeddings(chunks: list[dict], sentence_transformer: SentenceTransformerResource) -> list[dict]:
    if not chunks:
        return []

    return [
        {**chunk, "embedding": sentence_transformer.encode(chunk["content"])}
        for chunk in chunks
    ]
