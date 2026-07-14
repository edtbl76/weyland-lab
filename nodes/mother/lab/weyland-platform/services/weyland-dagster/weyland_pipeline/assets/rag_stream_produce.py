"""RAG streaming producer (B-RAG-STREAM step 4) — the reference-boundary compute unit.

Replaces the in-process chunks -> embeddings -> 5x *_write chain. For each CHANGED document it publishes a
`delete` (replace-clear) then one `upsert` per chunk to `rag.chunks`; for each REMOVED document it publishes a
`delete` (tombstone). The five store consumers apply those independently. Embedding is done ONCE, out of
Dagster, by the warm GPU service on rogueone — only the manifest + record stream cross this op (invariants I1,
I2, I3, I6). Change-detection + prune state live in `rag_manifest` (this op's own table), decoupled from the
pgvector store's `rag_documents` (see design §3.2b). aidlc-kb is structurally out of scope: source_document
never yields aidlc-kb/ paths and the manifest query excludes them, so the KB corpus can never be tombstoned.
"""
import os

import httpx
from confluent_kafka import KafkaError, KafkaException, SerializingProducer
from confluent_kafka.admin import AdminClient, NewTopic
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
from confluent_kafka.serialization import StringSerializer
from dagster import MetadataValue, Output, asset

from weyland_pipeline.assets.chunks import _code_chunks, _markdown_chunks
from weyland_pipeline.resources import PostgresResource

# Keep in sync with services/rag-index/schema.py (RAGCHUNK_SCHEMA) — same subject on the registry.
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
EMBED_URL = os.environ.get("EMBED_URL", "http://rogueone.weyland.lab:8900")
EMBED_BATCH = int(os.environ.get("EMBED_BATCH", "64"))
KB_PREFIX = "aidlc-kb/"


def _ensure_topic(bootstrap: str) -> None:
    admin = AdminClient({"bootstrap.servers": bootstrap})
    fut = admin.create_topics([NewTopic(TOPIC, num_partitions=3, replication_factor=1)])[TOPIC]
    try:
        fut.result()
    except KafkaException as e:
        if e.args[0].code() != KafkaError.TOPIC_ALREADY_EXISTS:
            raise


def _chunk(doc: dict) -> list[dict]:
    return _markdown_chunks(doc["content"]) if doc["kind"] == "markdown" else _code_chunks(doc["content"])


def _embed(texts: list[str]) -> list[list[float]]:
    """Batched calls to the warm rogueone embedding service."""
    out: list[list[float]] = []
    with httpx.Client(timeout=120) as client:
        for i in range(0, len(texts), EMBED_BATCH):
            resp = client.post(f"{EMBED_URL}/embed", json={"texts": texts[i:i + EMBED_BATCH]})
            resp.raise_for_status()
            out.extend(resp.json()["vectors"])
    return out


def _rec(source_path: str, op: str, run_id: str, **kw) -> dict:
    rec = {"source_path": source_path, "op": op, "chunk_index": None, "chunk_title": None,
           "chunk_text": None, "vector": None, "content_hash": None, "source_name": None,
           "kind": None, "run_id": run_id}
    rec.update(kw)
    return rec


@asset(
    group_name="rag",
    description="Streaming RAG producer: chunk+embed CHANGED docs, publish upserts+tombstones to rag.chunks. "
                "rag_manifest = change-detection + prune state; embedding is done on the rogueone GPU service.",
)
def rag_stream_produce(context, source_document: list[dict], content_hash: dict,
                       postgres: PostgresResource) -> Output[dict]:
    run_id = context.run_id
    bootstrap = os.environ["REDPANDA_BOOTSTRAP"]
    sr = SchemaRegistryClient({"url": os.environ["SCHEMA_REGISTRY_URL"]})
    _ensure_topic(bootstrap)
    producer = SerializingProducer({
        "bootstrap.servers": bootstrap,
        "key.serializer": StringSerializer("utf_8"),
        "value.serializer": AvroSerializer(sr, RAGCHUNK_SCHEMA),
    })

    current = {d["source_path"]: d for d in source_document}

    # Stored docs manifest (KB excluded — the producer never owns/prunes the aidlc-kb corpus).
    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS rag_manifest "
                        "(source_path text PRIMARY KEY, content_hash text NOT NULL)")
            cur.execute("SELECT source_path, content_hash FROM rag_manifest WHERE source_path NOT LIKE %s",
                        (KB_PREFIX + "%",))
            stored = dict(cur.fetchall())
        conn.commit()

    changed = [d for sp, d in current.items() if stored.get(sp) != content_hash[sp]]
    removed = [sp for sp in stored if sp not in current]

    upserts = 0
    for doc in changed:
        sp = doc["source_path"]
        producer.produce(topic=TOPIC, key=sp, value=_rec(sp, "delete", run_id))  # replace-clear
        cks = _chunk(doc)
        for c, vec in zip(cks, _embed([c["content"] for c in cks])):
            producer.produce(topic=TOPIC, key=sp, value=_rec(
                sp, "upsert", run_id, chunk_index=c["chunk_index"], chunk_title=c["chunk_title"],
                chunk_text=c["content"], vector=vec, content_hash=content_hash[sp],
                source_name=doc["source_name"], kind=doc["kind"]))
            upserts += 1
        producer.poll(0)

    for sp in removed:
        producer.produce(topic=TOPIC, key=sp, value=_rec(sp, "delete", run_id))  # tombstone

    producer.flush(60)

    # Manifest update AFTER a successful publish — publish-then-commit keeps at-least-once (a partial failure
    # re-publishes next run; every record is idempotent, so re-publishing is safe).
    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            for doc in changed:
                sp = doc["source_path"]
                cur.execute("INSERT INTO rag_manifest (source_path, content_hash) VALUES (%s, %s) "
                            "ON CONFLICT (source_path) DO UPDATE SET content_hash = EXCLUDED.content_hash",
                            (sp, content_hash[sp]))
            if removed:
                cur.execute("DELETE FROM rag_manifest WHERE source_path = ANY(%s)", (removed,))
        conn.commit()

    context.log.info(f"rag_stream_produce: {len(changed)} changed docs ({upserts} chunk upserts), "
                     f"{len(removed)} removed (tombstones)")
    return Output(
        {"changed_docs": len(changed), "chunk_upserts": upserts, "removed_docs": len(removed)},
        metadata={
            "changed_docs": MetadataValue.int(len(changed)),
            "chunk_upserts": MetadataValue.int(upserts),
            "removed_docs": MetadataValue.int(len(removed)),
        },
    )
