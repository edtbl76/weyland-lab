"""Deep contract v2, integration tier (B260): the golden path against REAL Postgres, Valkey, Redpanda and MinIO.

Run by the `integration-python` CI step (backends as sidecars). Each test talks to the real service; nothing here
is mocked, and conftest.py fails the run when a backend setting is missing.
"""
import json
import os
import uuid

from confluent_kafka import Consumer
from fastapi.testclient import TestClient

import backends
from main import ItemIn, Settings, create_app

ENV = os.environ


def test_postgres_is_the_store_behind_the_http_api():
    store = backends.PostgresItemStore(ENV["GOLDEN_DATABASE_URL"])
    with TestClient(create_app(Settings(greeting="hi"), store=store)) as c:
        made = c.post("/items", json={"name": "pg-item", "tags": ["x"]}).json()
        assert c.get(f"/items/{made['id']}").json() == made
        assert made in c.get("/items", params={"limit": 100}).json()["items"]
    reopened = backends.PostgresItemStore(ENV["GOLDEN_DATABASE_URL"])   # it survives a restart: it is stored
    reopened.open()
    try:
        assert reopened.get(made["id"]).name == "pg-item"
    finally:
        reopened.close()


def test_valkey_serves_the_second_read():
    store = backends.CachedItemStore(backends.PostgresItemStore(ENV["GOLDEN_DATABASE_URL"]), ENV["GOLDEN_VALKEY_URL"])
    store.open()
    try:
        made = store.create(ItemIn(name="cached"))
        assert store.get(made.id) == made and store.hits == 0      # first read: Postgres, then cached
        assert store.get(made.id) == made and store.hits == 1      # second read: Valkey
    finally:
        store.close()


def test_redpanda_receives_item_created():
    topic = f"items-{uuid.uuid4().hex[:8]}"
    store = backends.EventingItemStore(backends.PostgresItemStore(ENV["GOLDEN_DATABASE_URL"]),
                                       ENV["GOLDEN_KAFKA_BOOTSTRAP"], topic)
    store.open()
    try:
        made = store.create(ItemIn(name="evented"))
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
        event = json.loads(msg.value())
        assert event == {"type": "item.created", "item": made.model_dump()}
    finally:
        consumer.close()


def test_minio_stores_and_returns_an_attachment():
    att = backends.AttachmentStore(ENV["GOLDEN_S3_ENDPOINT"], ENV.get("GOLDEN_S3_BUCKET", "golden-items"),
                                   ENV["GOLDEN_S3_ACCESS_KEY"], ENV["GOLDEN_S3_SECRET_KEY"])
    att.ensure_bucket()
    att.put(7, b"attachment-bytes")
    assert att.get(7) == b"attachment-bytes"


def test_the_composed_store_comes_from_env():
    store = backends.build_store_from_env(ENV)
    assert type(store).__name__ == "EventingItemStore"            # Postgres, wrapped by the cache, then events
    assert type(backends.build_store_from_env({})).__name__ == "InMemoryItemStore"
