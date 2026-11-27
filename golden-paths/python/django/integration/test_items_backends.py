# GENERATED from golden-paths-shared/python/integration/test_items_backends.py by scripts/sync-golden-shared.sh: edit the source, not this copy.
"""Deep contract v2, integration tier: the framework-neutral adapters against REAL Postgres, Valkey, Redpanda and
MinIO (B260; shared since B261). Each path also has its own test of its HTTP API on Postgres.

SOURCE: golden-paths-shared/python/integration/. Each path holds a synced copy (scripts/sync-golden-shared.sh).
"""
import json
import os
import uuid

from confluent_kafka import Consumer

import items_backends

ENV = os.environ


def _postgres():
    return items_backends.PostgresItemStore(ENV["GOLDEN_DATABASE_URL"])


def test_postgres_stores_items_across_a_reopen():
    store = _postgres()
    store.open()
    try:
        made = store.create("pg-item", ["x"])
        assert store.get(made["id"]) == made and made in store.list(1000, 0)
    finally:
        store.close()
    reopened = _postgres()
    reopened.open()
    try:
        assert reopened.get(made["id"]) == made
    finally:
        reopened.close()


def test_valkey_serves_the_second_read():
    store = items_backends.CachedItemStore(_postgres(), ENV["GOLDEN_VALKEY_URL"])
    store.open()
    try:
        made = store.create("cached", [])
        assert store.get(made["id"]) == made and store.hits == 0      # first read: Postgres, then cached
        assert store.get(made["id"]) == made and store.hits == 1      # second read: Valkey
    finally:
        store.close()


def test_redpanda_receives_item_created():
    topic = f"items-{uuid.uuid4().hex[:8]}"
    store = items_backends.EventingItemStore(_postgres(), ENV["GOLDEN_KAFKA_BOOTSTRAP"], topic)
    store.open()
    try:
        made = store.create("evented", [])
    finally:
        store.close()
    consumer = Consumer({"bootstrap.servers": ENV["GOLDEN_KAFKA_BOOTSTRAP"], "group.id": topic,
                         "auto.offset.reset": "earliest"})
    consumer.subscribe([topic])
    try:
        msg = None
        for _ in range(30):
            msg = consumer.poll(1.0)
            if msg is not None and msg.error() is None:
                break
        assert msg is not None and msg.error() is None, "no item.created event arrived"
        assert json.loads(msg.value()) == {"type": "item.created", "item": made}
    finally:
        consumer.close()


def test_minio_stores_and_returns_an_attachment():
    att = items_backends.AttachmentStore(ENV["GOLDEN_S3_ENDPOINT"], ENV.get("GOLDEN_S3_BUCKET", "golden-items"),
                                         ENV["GOLDEN_S3_ACCESS_KEY"], ENV["GOLDEN_S3_SECRET_KEY"])
    att.ensure_bucket()
    att.put(7, b"attachment-bytes")
    assert att.get(7) == b"attachment-bytes"


def test_the_composed_store_comes_from_env():
    assert type(items_backends.build_store_from_env(ENV)).__name__ == "EventingItemStore"
    assert type(items_backends.build_store_from_env({})).__name__ == "InMemoryItemStore"
