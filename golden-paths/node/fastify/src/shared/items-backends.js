// GENERATED from golden-paths-shared/node/src/shared/items-backends.js by scripts/sync-golden-shared.sh: edit the source, not this copy.
// items-backends — real backends for the deep contract v2 ItemStore (B262; per ECOSYSTEM, not per framework).
//
// The golden paths run on InMemoryItemStore (items-store.js). A scaffolded service that needs real storage composes
// these, selected by env with `buildStoreFromEnv()`:
//
//   GOLDEN_DATABASE_URL     Postgres  -> PostgresItemStore (the source of truth; migrates its table on open)
//   GOLDEN_VALKEY_URL       Valkey    -> CachedItemStore   (read-through cache for get)
//   GOLDEN_KAFKA_BOOTSTRAP  Redpanda  -> EventingItemStore (publishes item.created to GOLDEN_KAFKA_TOPIC)
//   GOLDEN_S3_ENDPOINT      MinIO     -> AttachmentStore   (an item's attachment bytes; GOLDEN_S3_BUCKET, the keys and
//                                        GOLDEN_S3_REGION are config, never a literal)
//
// Node's frameworks share these clients (pg, ioredis, kafkajs, @aws-sdk/client-s3; owner-approved 2026-11-27). They
// are devDependencies of each path and are required lazily, so a path's unit lane and its image never load them; a
// service that uses a backend moves its client into `dependencies`. Proven only against real backends (integration/,
// the `integration-node` CI step), never a mock.
//
// SOURCE: golden-paths-shared/node/. Each path holds a synced copy (scripts/sync-golden-shared.sh); a guard fails CI if
// a copy drifts. Edit this file, never a copy.
'use strict';

const { InMemoryItemStore } = require('./items-store');

const TABLE = `CREATE TABLE IF NOT EXISTS items (
    id   BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL CHECK (char_length(name) BETWEEN 1 AND 64),
    tags TEXT[] NOT NULL DEFAULT '{}'
)`;

// BIGSERIAL comes back as a string from pg (it can exceed 2^53); item ids here are well inside a safe integer.
const row = (r) => ({ id: Number(r.id), name: r.name, tags: [...r.tags] });

/** The ItemStore on Postgres (pg). One client: a template, not a pool tuning guide. */
class PostgresItemStore {
  constructor(url) {
    this.url = url;
    this.client = null;
  }

  async open() {
    const { Client } = require('pg');
    this.client = new Client({ connectionString: this.url });
    await this.client.connect();
    await this.client.query(TABLE);
  }

  async close() {
    if (this.client) await this.client.end();
  }

  async create(name, tags) {
    const { rows } = await this.client.query(
      'INSERT INTO items (name, tags) VALUES ($1, $2) RETURNING id, name, tags', [name, tags]);
    return row(rows[0]);
  }

  async get(id) {
    const { rows } = await this.client.query('SELECT id, name, tags FROM items WHERE id = $1', [id]);
    return rows.length ? row(rows[0]) : null;
  }

  async list(limit, offset) {
    const { rows } = await this.client.query(
      'SELECT id, name, tags FROM items ORDER BY id LIMIT $1 OFFSET $2', [limit, offset]);
    return rows.map(row);
  }
}

/** A read-through Valkey cache in front of another store (ioredis speaks Valkey's protocol). */
class CachedItemStore {
  constructor(inner, url, ttlS = 60) {
    Object.assign(this, { inner, url, ttlS, cache: null, hits: 0 });
  }

  async open() {
    const { Redis } = require('ioredis');
    await this.inner.open();
    // lazyConnect + an explicit connect: fail at startup, not on the first request; no endless reconnect loop.
    this.cache = new Redis(this.url, { lazyConnect: true, maxRetriesPerRequest: 1 });
    await this.cache.connect();
    await this.cache.ping();
  }

  async close() {
    if (this.cache) await this.cache.quit();
    await this.inner.close();
  }

  create(name, tags) {
    return this.inner.create(name, tags);
  }

  async get(id) {
    const cached = await this.cache.get(`item:${id}`);
    if (cached !== null) {
      this.hits += 1;
      return JSON.parse(cached);
    }
    const found = await this.inner.get(id);
    if (found) await this.cache.set(`item:${id}`, JSON.stringify(found), 'EX', this.ttlS);
    return found;
  }

  list(limit, offset) {
    return this.inner.list(limit, offset);
  }
}

/** Publishes `item.created` to Kafka (Redpanda) after each create; the write is the inner store's. */
class EventingItemStore {
  constructor(inner, bootstrap, topic) {
    Object.assign(this, { inner, bootstrap, topic, producer: null });
  }

  async open() {
    const { Kafka, logLevel } = require('kafkajs');
    await this.inner.open();
    const kafka = new Kafka({ clientId: 'golden-items', brokers: this.bootstrap.split(','), logLevel: logLevel.WARN });
    this.producer = kafka.producer({ allowAutoTopicCreation: true });
    await this.producer.connect();
  }

  async close() {
    if (this.producer) await this.producer.disconnect();
    await this.inner.close();
  }

  async create(name, tags) {
    const created = await this.inner.create(name, tags);
    // acks -1 (all): send() resolves only once the event is durable and rejects otherwise, so an undelivered
    // event is an error on this request, never silent.
    await this.producer.send({
      topic: this.topic, acks: -1,
      messages: [{ key: String(created.id), value: JSON.stringify({ type: 'item.created', item: created }) }],
    });
    return created;
  }

  get(id) {
    return this.inner.get(id);
  }

  list(limit, offset) {
    return this.inner.list(limit, offset);
  }
}

/** An item's attachment in S3 (MinIO), keyed by item id. */
class AttachmentStore {
  constructor({ endpoint, bucket, accessKey, secretKey, region }) {
    const { S3Client } = require('@aws-sdk/client-s3');
    this.bucket = bucket;
    this.s3 = new S3Client({
      endpoint, region, forcePathStyle: true,          // MinIO serves buckets by path, not by subdomain
      credentials: { accessKeyId: accessKey, secretAccessKey: secretKey },
    });
  }

  async ensureBucket() {
    const { ListBucketsCommand, CreateBucketCommand } = require('@aws-sdk/client-s3');
    const { Buckets = [] } = await this.s3.send(new ListBucketsCommand({}));
    if (!Buckets.some((b) => b.Name === this.bucket)) {
      await this.s3.send(new CreateBucketCommand({ Bucket: this.bucket }));
    }
  }

  async put(id, data) {
    const { PutObjectCommand } = require('@aws-sdk/client-s3');
    await this.s3.send(new PutObjectCommand({ Bucket: this.bucket, Key: `items/${id}`, Body: data }));
  }

  async get(id) {
    const { GetObjectCommand } = require('@aws-sdk/client-s3');
    const out = await this.s3.send(new GetObjectCommand({ Bucket: this.bucket, Key: `items/${id}` }));
    return Buffer.from(await out.Body.transformToByteArray());
  }

  close() {
    this.s3.destroy();
  }
}

/** The composed store the env asks for; the in-memory store when no backend is configured. */
function buildStoreFromEnv(env = process.env) {
  if (!env.GOLDEN_DATABASE_URL) return new InMemoryItemStore();
  let store = new PostgresItemStore(env.GOLDEN_DATABASE_URL);
  if (env.GOLDEN_VALKEY_URL) store = new CachedItemStore(store, env.GOLDEN_VALKEY_URL);
  if (env.GOLDEN_KAFKA_BOOTSTRAP) {
    store = new EventingItemStore(store, env.GOLDEN_KAFKA_BOOTSTRAP, env.GOLDEN_KAFKA_TOPIC || 'items');
  }
  return store;
}

module.exports = { PostgresItemStore, CachedItemStore, EventingItemStore, AttachmentStore, buildStoreFromEnv };
