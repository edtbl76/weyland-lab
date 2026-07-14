"""RagChunk — the single Avro record on topic `rag.chunks` (B-RAG-STREAM).

Two record types share one schema, discriminated by `op`:
  - "upsert": carries chunk_index / chunk_text / vector / ... — index one chunk into a store.
  - "delete": carries only source_path — clear ALL of a document's rows from a store. Emitted BOTH for a
    removed document (final delete) AND as the replace-clear that precedes a changed document's new chunks.
    Because the topic is keyed by source_path, a doc's delete is ordered before its re-chunk upserts on the
    same partition — reproducing the old delete-then-upsert "replace document" semantics, per store, streaming.
"""

RAGCHUNK_SCHEMA = """
{
  "type": "record",
  "name": "RagChunk",
  "namespace": "weyland.rag",
  "fields": [
    {"name": "source_path",  "type": "string"},
    {"name": "op",           "type": "string"},
    {"name": "chunk_index",  "type": ["null", "int"],    "default": null},
    {"name": "chunk_title",  "type": ["null", "string"], "default": null},
    {"name": "chunk_text",   "type": ["null", "string"], "default": null},
    {"name": "vector",       "type": ["null", {"type": "array", "items": "float"}], "default": null},
    {"name": "content_hash", "type": ["null", "string"], "default": null},
    {"name": "source_name",  "type": ["null", "string"], "default": null},
    {"name": "kind",         "type": ["null", "string"], "default": null},
    {"name": "run_id",       "type": ["null", "string"], "default": null}
  ]
}
"""

TOPIC = "rag.chunks"
