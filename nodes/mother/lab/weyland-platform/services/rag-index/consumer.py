"""RAG index consumer (B-RAG-STREAM) — one image, many stores.

Reads `rag.chunks` (Confluent-Avro) and applies each record to ONE store, selected by the STORE env var.
Same binary, five Deployments (STORE=qdrant|weaviate|pgvector|neo4j|opensearch), each its own consumer group
— so a store being down or slow never blocks the others (invariant I4). Manual offset commit AFTER the record
is applied → at-least-once; combined with idempotent upsert (deterministic id) + idempotent delete-by-path,
that is effectively-once (invariant: §4.2 of the design).
"""
import os
import sys

from confluent_kafka import DeserializingConsumer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer
from confluent_kafka.serialization import StringDeserializer

from schema import RAGCHUNK_SCHEMA, TOPIC
from stores import get_handler

STORE = os.environ["STORE"]
GROUP_ID = os.environ.get("GROUP_ID", f"rag-index-{STORE}")
BOOTSTRAP = os.environ["REDPANDA_BOOTSTRAP"]
SCHEMA_REGISTRY_URL = os.environ["SCHEMA_REGISTRY_URL"]


def main() -> None:
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
            msg = consumer.poll(1.0)
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
