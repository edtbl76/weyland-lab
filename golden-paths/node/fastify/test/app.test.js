// Contract self-test (Fastify). Exercises all four endpoints via app.inject() — no live port.
'use strict';

const { test } = require('node:test');
const assert = require('node:assert');
const { build, SERVICE_NAME } = require('../src/app');

test('health is ok', async () => {
  const app = build();
  const res = await app.inject({ method: 'GET', url: '/health' });
  assert.strictEqual(res.statusCode, 200);
  assert.strictEqual(res.json().status, 'ok');
  await app.close();
});

test('ready is ready', async () => {
  const app = build();
  const res = await app.inject({ method: 'GET', url: '/ready' });
  assert.strictEqual(res.statusCode, 200);
  assert.strictEqual(res.json().status, 'ready');
  await app.close();
});

test('hello returns the known payload', async () => {
  const app = build();
  const res = await app.inject({ method: 'GET', url: '/hello' });
  assert.strictEqual(res.statusCode, 200);
  assert.deepStrictEqual(res.json(), { service: SERVICE_NAME, message: 'hello, weyland' });
  await app.close();
});

test('metrics exposes prometheus', async () => {
  const app = build();
  await app.inject({ method: 'GET', url: '/hello' });
  const res = await app.inject({ method: 'GET', url: '/metrics' });
  assert.strictEqual(res.statusCode, 200);
  assert.ok(res.body.includes('golden_hello_requests_total'));
  await app.close();
});
