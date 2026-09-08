// Contract self-test (Express). Exercises all four endpoints over supertest — no live port.
'use strict';

const request = require('supertest');
const { createApp, SERVICE_NAME } = require('../src/app');

const app = createApp();

test('health is ok', async () => {
  const res = await request(app).get('/health');
  expect(res.status).toBe(200);
  expect(res.body.status).toBe('ok');
});

test('ready is ready', async () => {
  const res = await request(app).get('/ready');
  expect(res.status).toBe(200);
  expect(res.body.status).toBe('ready');
});

test('hello returns the known payload', async () => {
  const res = await request(app).get('/hello');
  expect(res.status).toBe(200);
  expect(res.body).toEqual({ service: SERVICE_NAME, message: 'hello, weyland' });
});

test('metrics exposes prometheus', async () => {
  await request(app).get('/hello');
  const res = await request(app).get('/metrics');
  expect(res.status).toBe(200);
  expect(res.text).toContain('golden_hello_requests_total');
});
