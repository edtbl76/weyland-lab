"""Kafka/Avro producer (B1.5 streaming) — replays the STREAM-shaped silver datasets as Avro events into
Redpanda topics, registering each schema in the broker's built-in Schema Registry. Uses confluent-kafka's
AvroSerializer → **Confluent wire format** (magic byte + schema id), so Redpanda Console and any standard Avro
consumer decode the messages against the registry (a raw fastavro payload wouldn't be decodable by them).

This is the "Avro in motion" demo (B73) + the grid Redpanda column. It's a BOUNDED replay (cap per dataset) —
it proves the Avro + Schema-Registry + produce mechanics and feeds a consumer; genuinely event-driven change
data comes later via Debezium CDC. Topic: `datasets.<domain>.<dataset>`, 3 partitions (consumer-group story),
RF=1 (single node). Memory-safe: parquet iter_batches, never the whole table."""
import json
import os
import tempfile

import pyarrow.parquet as pq

from . import io
from .writers import _AVRO_TYPE

_POLL_EVERY = 10_000


def _avro_schema(arrow_schema, record_name):
    """Arrow schema → an Avro record JSON string (all fields nullable union, mirroring write_avro). Also returns
    the set of columns whose Avro type is 'string' but whose arrow type isn't — their values must be str-coerced."""
    fields = [{"name": f.name, "type": ["null", _AVRO_TYPE.get(str(f.type), "string")], "default": None}
              for f in arrow_schema]
    str_cols = {f.name for f in arrow_schema
                if _AVRO_TYPE.get(str(f.type), "string") == "string" and str(f.type) not in ("string", "large_string")}
    return json.dumps({"type": "record", "name": record_name, "fields": fields}), str_cols


def _ensure_topic(bootstrap, topic):
    from confluent_kafka.admin import AdminClient, NewTopic

    admin = AdminClient({"bootstrap.servers": bootstrap})
    fut = admin.create_topics([NewTopic(topic, num_partitions=3, replication_factor=1)])[topic]
    try:
        fut.result()   # blocks until created
    except Exception as e:  # noqa: BLE001 — "already exists" is fine; anything else surfaces on produce
        if "already exists" not in str(e).lower():
            raise


def _produce_dataset(cfg, dataset, spec, log) -> dict:
    from confluent_kafka import Producer
    from confluent_kafka.schema_registry import SchemaRegistryClient
    from confluent_kafka.schema_registry.avro import AvroSerializer
    from confluent_kafka.serialization import MessageField, SerializationContext

    bootstrap = os.environ["REDPANDA_BOOTSTRAP"]
    sr = SchemaRegistryClient({"url": os.environ["SCHEMA_REGISTRY_URL"]})
    topic = f"datasets.{cfg.domain}.{dataset}"
    key_col, cap = spec.get("key"), spec.get("cap")

    mc = io.client()
    prefix = f"{io.branch()}/parquet/{dataset}/"
    objs = [o.object_name for o in mc.list_objects(cfg.repo, prefix=prefix, recursive=True)
            if o.object_name.endswith(".parquet")]
    if not objs:
        return {topic: "ERROR: no silver parquet"}

    _ensure_topic(bootstrap, topic)
    producer = Producer({"bootstrap.servers": bootstrap, "linger.ms": 50, "queue.buffering.max.messages": 200_000})

    n, ser, str_cols = 0, None, set()
    for obj in objs:
        tmp = tempfile.NamedTemporaryFile(suffix=".parquet", delete=False)
        tmp.close()
        try:
            mc.fget_object(cfg.repo, obj.object_name, tmp.name)
            pf = pq.ParquetFile(tmp.name)
            if ser is None:   # schema from the first file (all files share it)
                schema_str, str_cols = _avro_schema(pf.schema_arrow, f"datasets_{cfg.domain}_{dataset}_record")
                ser = AvroSerializer(sr, schema_str, lambda obj, ctx: obj)
                log.info(f"{topic}: registering Avro schema ({len(pf.schema_arrow.names)} fields)")
            done = False
            for batch in pf.iter_batches(batch_size=10_000):
                for row in batch.to_pylist():
                    for c in str_cols:
                        if row.get(c) is not None:
                            row[c] = str(row[c])
                    key = str(row[key_col]).encode() if key_col and row.get(key_col) is not None else None
                    producer.produce(topic=topic, key=key,
                                     value=ser(row, SerializationContext(topic, MessageField.VALUE)))
                    n += 1
                    if n % _POLL_EVERY == 0:
                        producer.poll(0)
                    if cap and n >= cap:
                        done = True
                        break
                if done:
                    break
            if done:
                break
        finally:
            os.unlink(tmp.name)
    producer.flush(30)
    log.info(f"{topic}: produced {n:,} Avro events" + (f" (capped at {cap:,})" if cap and n >= cap else ""))
    return {topic: n}


def build_stream_produce_assets(cfg):
    """One producer asset per domain (datasets_<domain>_stream_produce) that replays every stream_allow dataset
    to its Redpanda topic. Own stores group → runs in the hydrate job, not the transform."""
    from dagster import MetadataValue, Output, asset

    if not cfg.stream_allow:
        return []
    d = cfg.domain
    deps = [f"datasets_{d}_parquet"] + [
        f"datasets_{d}_{ds}_parquet" for ds in sorted(set(cfg.stream_allow) & cfg.streamed_parquet)]

    @asset(
        name=f"datasets_{d}_stream_produce",
        group_name=f"datasets_{d}_stores",
        deps=deps,
        description=f"Replay stream-shaped silver → Redpanda Avro topics ({len(cfg.stream_allow)} datasets).",
    )
    def _stream_produce(context):
        out = {}
        for dataset, spec in sorted(cfg.stream_allow.items()):
            try:
                out.update(_produce_dataset(cfg, dataset, spec, context.log))
            except Exception as e:  # noqa: BLE001 — per-dataset resilience
                out[f"datasets.{d}.{dataset}"] = f"ERROR: {e}"
                context.log.error(f"stream {dataset}: {e}")
        ok = sum(1 for v in out.values() if isinstance(v, int))
        return Output(out, metadata={
            "topics_produced": MetadataValue.int(ok),
            "events_total": MetadataValue.int(sum(v for v in out.values() if isinstance(v, int))),
            "detail": MetadataValue.json(out),
        })

    return [_stream_produce]
