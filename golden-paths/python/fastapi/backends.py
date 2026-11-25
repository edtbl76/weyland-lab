"""Real backends for the golden path's ItemStore — the deep contract v2 integration tier (B260).

The template runs on InMemoryItemStore (main.py). A scaffolded service that needs real storage composes these,
selected by env (`build_store_from_env`), and serves `uvicorn backends:app`:

  GOLDEN_DATABASE_URL     Postgres  -> PostgresItemStore (the source of truth; migrates its table on open)
  GOLDEN_VALKEY_URL       Valkey    -> CachedItemStore   (read-through cache for GET /items/{id})
  GOLDEN_KAFKA_BOOTSTRAP  Redpanda  -> EventingItemStore (publishes item.created to GOLDEN_KAFKA_TOPIC)
  GOLDEN_S3_ENDPOINT      MinIO     -> AttachmentStore   (an item's attachment bytes; with GOLDEN_S3_BUCKET + keys)

Python's frameworks share these clients, so this module is per ECOSYSTEM, not per framework
(docs/concepts/golden-path-capabilities.md § integration tier). It is proven only against real backends
(integration/, the `integration-python` CI step); the unit lane never imports it, and it never mocks a backend.
Clients (owner-approved 2026-11-25): requirements-integration.txt.
"""
from __future__ import annotations

import json
import os
import threading

from main import InMemoryItemStore, Item, ItemIn, create_app  # noqa: F401  (InMemoryItemStore: the fallback)

_TABLE = """CREATE TABLE IF NOT EXISTS items (
    id   BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL CHECK (char_length(name) BETWEEN 1 AND 64),
    tags TEXT[] NOT NULL DEFAULT '{}'
)"""


class PostgresItemStore:
    """The ItemStore on Postgres (psycopg 3). One connection, serialised: a template, not a pool tuning guide."""

    def __init__(self, dsn: str) -> None:
        self._dsn, self._conn, self._lock = dsn, None, threading.Lock()

    def open(self) -> None:
        import psycopg
        self._conn = psycopg.connect(self._dsn, autocommit=True)
        with self._lock:
            self._conn.execute(_TABLE)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()

    def create(self, item: ItemIn) -> Item:
        with self._lock:
            row = self._conn.execute("INSERT INTO items (name, tags) VALUES (%s, %s) RETURNING id",
                                     (item.name, item.tags)).fetchone()
        return Item(id=row[0], **item.model_dump())

    def get(self, item_id: int) -> Item | None:
        with self._lock:
            row = self._conn.execute("SELECT id, name, tags FROM items WHERE id = %s", (item_id,)).fetchone()
        return Item(id=row[0], name=row[1], tags=row[2]) if row else None

    def list(self, limit: int, offset: int) -> list[Item]:
        with self._lock:
            rows = self._conn.execute("SELECT id, name, tags FROM items ORDER BY id LIMIT %s OFFSET %s",
                                      (limit, offset)).fetchall()
        return [Item(id=r[0], name=r[1], tags=r[2]) for r in rows]


class CachedItemStore:
    """A read-through Valkey cache in front of another store (redis-py speaks Valkey's protocol)."""

    def __init__(self, inner, url: str, ttl_s: int = 60) -> None:
        self._inner, self._url, self._ttl, self._cache = inner, url, ttl_s, None
        self.hits = 0

    def open(self) -> None:
        import redis
        self._inner.open()
        self._cache = redis.Redis.from_url(self._url)
        self._cache.ping()                       # fail at startup, not on the first request

    def close(self) -> None:
        if self._cache is not None:
            self._cache.close()
        self._inner.close()

    def create(self, item: ItemIn) -> Item:
        return self._inner.create(item)

    def get(self, item_id: int) -> Item | None:
        cached = self._cache.get(f"item:{item_id}")
        if cached is not None:
            self.hits += 1
            return Item.model_validate_json(cached)
        found = self._inner.get(item_id)
        if found is not None:
            self._cache.set(f"item:{item_id}", found.model_dump_json(), ex=self._ttl)
        return found

    def list(self, limit: int, offset: int) -> list[Item]:
        return self._inner.list(limit, offset)


class EventingItemStore:
    """Publishes `item.created` to Kafka (Redpanda) after each create; the write is the inner store's."""

    def __init__(self, inner, bootstrap: str, topic: str) -> None:
        self._inner, self._bootstrap, self._topic, self._producer = inner, bootstrap, topic, None

    def open(self) -> None:
        from confluent_kafka import Producer
        self._inner.open()
        self._producer = Producer({"bootstrap.servers": self._bootstrap, "acks": "all"})

    def close(self) -> None:
        if self._producer is not None:
            self._producer.flush(10)
        self._inner.close()

    def create(self, item: ItemIn) -> Item:
        created = self._inner.create(item)
        failures = []
        self._producer.produce(self._topic, key=str(created.id),
                               value=json.dumps({"type": "item.created", "item": created.model_dump()}),
                               on_delivery=lambda err, _msg: err and failures.append(err))
        if self._producer.flush(10) != 0 or failures:   # an undelivered event is an error, never silent
            raise RuntimeError(f"item.created for {created.id} was not delivered: {failures or 'flush timed out'}")
        return created

    def get(self, item_id: int) -> Item | None:
        return self._inner.get(item_id)

    def list(self, limit: int, offset: int) -> list[Item]:
        return self._inner.list(limit, offset)


class AttachmentStore:
    """An item's attachment in S3 (MinIO), keyed by item id."""

    def __init__(self, endpoint: str, bucket: str, access_key: str, secret_key: str) -> None:
        import boto3
        self._bucket = bucket
        self._s3 = boto3.client("s3", endpoint_url=endpoint, aws_access_key_id=access_key,
                                aws_secret_access_key=secret_key, region_name="us-east-1")

    def ensure_bucket(self) -> None:
        names = {b["Name"] for b in self._s3.list_buckets().get("Buckets", [])}
        if self._bucket not in names:
            self._s3.create_bucket(Bucket=self._bucket)

    def put(self, item_id: int, data: bytes) -> None:
        self._s3.put_object(Bucket=self._bucket, Key=f"items/{item_id}", Body=data)

    def get(self, item_id: int) -> bytes:
        return self._s3.get_object(Bucket=self._bucket, Key=f"items/{item_id}")["Body"].read()


def build_store_from_env(env=os.environ):
    """The composed store the env asks for; the in-memory store when no backend is configured."""
    if not env.get("GOLDEN_DATABASE_URL"):
        return InMemoryItemStore()
    store = PostgresItemStore(env["GOLDEN_DATABASE_URL"])
    if env.get("GOLDEN_VALKEY_URL"):
        store = CachedItemStore(store, env["GOLDEN_VALKEY_URL"])
    if env.get("GOLDEN_KAFKA_BOOTSTRAP"):
        store = EventingItemStore(store, env["GOLDEN_KAFKA_BOOTSTRAP"], env.get("GOLDEN_KAFKA_TOPIC", "items"))
    return store


def create_backed_app():
    return create_app(store=build_store_from_env())


app = create_backed_app() if os.environ.get("GOLDEN_DATABASE_URL") else None
