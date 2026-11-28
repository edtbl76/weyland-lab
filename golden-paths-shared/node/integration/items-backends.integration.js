// Deep contract v2, integration tier: the framework-neutral adapters against REAL Postgres, Valkey, Redpanda and
// MinIO (B262). Each path also has its own test of its HTTP API on Postgres (api-postgres.integration.js).
//
// Named *.integration.js, never *.test.js: `node --test` and jest discover *.test.* by default, and these need real
// backends, so the unit lanes never pick them up; the `integration-node` CI step names them explicitly. A missing
// backend setting fails the run: an unchecked backend is never "passed".
//
// SOURCE: golden-paths-shared/node/integration/. Each path holds a synced copy (scripts/sync-golden-shared.sh).
'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const backends = require('../src/shared/items-backends');

const REQUIRED = ['GOLDEN_DATABASE_URL', 'GOLDEN_VALKEY_URL', 'GOLDEN_KAFKA_BOOTSTRAP', 'GOLDEN_S3_ENDPOINT',
  'GOLDEN_S3_ACCESS_KEY', 'GOLDEN_S3_SECRET_KEY'];
const missing = REQUIRED.filter((k) => !process.env[k]);
if (missing.length) {
  throw new Error(`integration tier: backend settings missing (${missing.join(', ')}); refusing to run `
    + '(an unchecked backend is never "passed")');
}
const ENV = process.env;
const postgres = () => new backends.PostgresItemStore(ENV.GOLDEN_DATABASE_URL);

test('postgres stores items across a reopen', async () => {
  const store = postgres();
  await store.open();
  let made;
  try {
    made = await store.create('pg-item', ['x']);
    assert.deepEqual(await store.get(made.id), made);
    assert.ok((await store.list(1000, 0)).some((i) => i.id === made.id));
  } finally {
    await store.close();
  }
  const reopened = postgres();
  await reopened.open();
  try {
    assert.deepEqual(await reopened.get(made.id), made);
  } finally {
    await reopened.close();
  }
});

test('valkey serves the second read', async () => {
  const store = new backends.CachedItemStore(postgres(), ENV.GOLDEN_VALKEY_URL);
  await store.open();
  try {
    const made = await store.create('cached', []);
    assert.deepEqual(await store.get(made.id), made);
    assert.equal(store.hits, 0);                         // first read: Postgres, then cached
    assert.deepEqual(await store.get(made.id), made);
    assert.equal(store.hits, 1);                         // second read: Valkey
  } finally {
    await store.close();
  }
});

test('redpanda receives item.created', async () => {
  const { Kafka, logLevel } = require('kafkajs');
  const topic = `items-${randomUUID().slice(0, 8)}`;
  const store = new backends.EventingItemStore(postgres(), ENV.GOLDEN_KAFKA_BOOTSTRAP, topic);
  await store.open();
  let made;
  try {
    made = await store.create('evented', []);
  } finally {
    await store.close();
  }
  const kafka = new Kafka({ clientId: 'golden-it', brokers: ENV.GOLDEN_KAFKA_BOOTSTRAP.split(','), logLevel: logLevel.WARN });
  const consumer = kafka.consumer({ groupId: topic });
  await consumer.connect();
  try {
    await consumer.subscribe({ topic, fromBeginning: true });
    const event = await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('no item.created event arrived within 30s')), 30000);
      consumer.run({ eachMessage: async ({ message }) => { clearTimeout(timer); resolve(JSON.parse(message.value)); } });
    });
    assert.deepEqual(event, { type: 'item.created', item: made });
  } finally {
    await consumer.disconnect();
  }
});

test('minio stores and returns an attachment', async () => {
  const att = new backends.AttachmentStore({
    endpoint: ENV.GOLDEN_S3_ENDPOINT, bucket: ENV.GOLDEN_S3_BUCKET || 'golden-items',
    accessKey: ENV.GOLDEN_S3_ACCESS_KEY, secretKey: ENV.GOLDEN_S3_SECRET_KEY, region: ENV.GOLDEN_S3_REGION || 'us-east-1',
  });
  try {
    await att.ensureBucket();
    await att.put(7, Buffer.from('attachment-bytes'));
    assert.equal((await att.get(7)).toString(), 'attachment-bytes');
  } finally {
    att.close();
  }
});

test('the composed store comes from env', () => {
  assert.equal(backends.buildStoreFromEnv(ENV).constructor.name, 'EventingItemStore');
  assert.equal(backends.buildStoreFromEnv({}).constructor.name, 'InMemoryItemStore');
});
