"""Step-3 spine probe — publish synthetic RagChunk records to `rag.chunks` WITHOUT the real producer/embed,
so the consumer→store path can be validated in isolation. Ships in the image; run via kubectl exec.

  python probe.py upsert   # delete-clear + 2 upserts for PROBE/spine.md  (expect 2 points in qdrant)
  python probe.py delete   # delete for PROBE/spine.md                    (expect 0 points)

Uses the exact serializer/topic conventions as the dataset streaming_producer (Confluent wire format).
"""
import os
import sys

from confluent_kafka import SerializingProducer
from confluent_kafka.admin import AdminClient, NewTopic
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
from confluent_kafka.serialization import StringSerializer

from schema import RAGCHUNK_SCHEMA, TOPIC

BOOTSTRAP = os.environ["REDPANDA_BOOTSTRAP"]
SCHEMA_REGISTRY_URL = os.environ["SCHEMA_REGISTRY_URL"]
SOURCE_PATH = "PROBE/spine.md"


def _ensure_topic():
    admin = AdminClient({"bootstrap.servers": BOOTSTRAP})
    fut = admin.create_topics([NewTopic(TOPIC, num_partitions=3, replication_factor=1)])[TOPIC]
    try:
        fut.result()
    except Exception as e:  # noqa: BLE001 — already-exists is fine
        if "already exists" not in str(e).lower():
            raise


def _base(op):
    return {"source_path": SOURCE_PATH, "op": op, "chunk_index": None, "chunk_title": None,
            "chunk_text": None, "vector": None, "content_hash": None, "source_name": None,
            "kind": None, "run_id": "probe"}


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "upsert"
    _ensure_topic()
    sr = SchemaRegistryClient({"url": SCHEMA_REGISTRY_URL})
    producer = SerializingProducer({
        "bootstrap.servers": BOOTSTRAP,
        "key.serializer": StringSerializer("utf_8"),
        "value.serializer": AvroSerializer(sr, RAGCHUNK_SCHEMA),
    })

    records = [_base("delete")]   # clear first (replace semantics), always
    if mode == "upsert":
        for i in range(2):
            r = _base("upsert")
            r.update(chunk_index=i, chunk_title=f"probe {i}", chunk_text=f"probe chunk {i}",
                     vector=[0.01 * (i + 1)] * 384, source_name="spine.md", kind="markdown")
            records.append(r)

    for r in records:
        producer.produce(topic=TOPIC, key=SOURCE_PATH, value=r)
    producer.flush(30)
    print(f"[probe] published {len(records)} records (mode={mode}) for {SOURCE_PATH}", flush=True)


if __name__ == "__main__":
    main()
