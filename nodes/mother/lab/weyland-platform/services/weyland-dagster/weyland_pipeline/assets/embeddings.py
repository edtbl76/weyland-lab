from dagster import asset
from weyland_pipeline.resources import SentenceTransformerResource
from weyland_pipeline.assets.chunks import embed_text


@asset(description="Embed each chunk using BAAI/bge-small-en-v1.5 (B74: embeds a topic-prefixed header, stores raw content). Returns empty list if chunks is empty.")
def embeddings(chunks: list[dict], sentence_transformer: SentenceTransformerResource) -> list[dict]:
    if not chunks:
        return []

    return [
        {**chunk, "embedding": sentence_transformer.encode(embed_text(chunk))}
        for chunk in chunks
    ]
