"""Store-handler factory. One handler per STORE; each exposes ensure() / on_upsert(rec) / on_delete(path).
Step 3 ships qdrant; weaviate/pgvector/neo4j/opensearch land in Step 5 (same interface)."""


def get_handler(store: str):
    if store == "qdrant":
        from stores.qdrant_store import QdrantHandler
        return QdrantHandler()
    raise ValueError(f"unknown STORE={store!r} (implemented: qdrant)")
