"""RAG index consumer (B-RAG-STREAM) — one image, many stores.

Reads `rag.chunks` (Confluent-Avro) and applies each record to ONE store, selected by the STORE env var.
Same binary, five Deployments (STORE=qdrant|weaviate|pgvector|neo4j|opensearch), each its own consumer group
— so a store being down or slow never blocks the others (invariant I4). Manual offset commit AFTER the record
is applied → at-least-once; combined with idempotent upsert (deterministic id) + idempotent delete-by-path,
that is effectively-once (invariant: §4.2 of the design).
"""
import os
import sys
import time

from confluent_kafka import DeserializingConsumer
from confluent_kafka.admin import AdminClient, NewTopic
from confluent_kafka.error import ConsumeError
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer
from confluent_kafka.serialization import StringDeserializer

from schema import RAGCHUNK_SCHEMA, TOPIC
from stores import get_handler

STORE = os.environ["STORE"]
GROUP_ID = os.environ.get("GROUP_ID", f"rag-index-{STORE}")
BOOTSTRAP = os.environ["REDPANDA_BOOTSTRAP"]
SCHEMA_REGISTRY_URL = os.environ["SCHEMA_REGISTRY_URL"]


def _ensure_topic() -> None:
    """Create rag.chunks if absent (3 partitions, RF=1 — same as the dataset producer). Idempotent: a consumer
    may start before any producer, and confluent-kafka raises on poll() of an unknown topic, so we bootstrap it
    here rather than crash-loop waiting for a producer."""
    admin = AdminClient({"bootstrap.servers": BOOTSTRAP})
    fut = admin.create_topics([NewTopic(TOPIC, num_partitions=3, replication_factor=1)])[TOPIC]
    try:
        fut.result()
    except Exception as e:  # noqa: BLE001 — already-exists is fine
        if "already exists" not in str(e).lower():
            raise


def main() -> None:
    _ensure_topic()
    sr = SchemaRegistryClient({"url": SCHEMA_REGISTRY_URL})
    avro_deser = AvroDeserializer(sr, RAGCHUNK_SCHEMA)

    consumer = DeserializingConsumer({
        "bootstrap.servers": BOOTSTRAP,
        "group.id": GROUP_ID,
        "key.deserializer": StringDeserializer("utf_8"),
        "value.deserializer": avro_deser,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,   # commit only after the store apply succeeds
    })

    handler = get_handler(STORE)
    handler.ensure()
    consumer.subscribe([TOPIC])
    print(f"[rag-index/{STORE}] group={GROUP_ID} subscribed to {TOPIC}", flush=True)

    try:
        while True:
            try:
                msg = consumer.poll(1.0)
            except ConsumeError as e:  # transient (e.g. topic metadata not yet propagated) — log + retry
                print(f"[rag-index/{STORE}] poll: {e}", file=sys.stderr, flush=True)
                time.sleep(1)
                continue
            if msg is None:
                continue
            if msg.error():
                print(f"[rag-index/{STORE}] consume error: {msg.error()}", file=sys.stderr, flush=True)
                continue
            rec = msg.value()
            try:
                if rec["op"] == "delete":
                    handler.on_delete(rec["source_path"])
                elif rec["op"] == "upsert":
                    handler.on_upsert(rec)
                else:
                    print(f"[rag-index/{STORE}] unknown op {rec['op']!r} — skipping", file=sys.stderr, flush=True)
                consumer.commit(msg)   # sync commit AFTER apply
            except Exception as e:  # noqa: BLE001 — surface + do NOT commit, so the record is retried
                print(f"[rag-index/{STORE}] apply failed for {rec.get('source_path')}: {e}",
                      file=sys.stderr, flush=True)
    finally:
        consumer.close()


if __name__ == "__main__":
    main()
