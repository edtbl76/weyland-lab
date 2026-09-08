// Golden path — Node / Express (B153). Runnable, ephemeral, extendable. Conforms to the golden-path
// contract (docs/design/golden-paths.md): GET /health /ready /metrics /hello.
// Scaffold FROM it: scripts/new-service.sh node/express <your-service>.
'use strict';

const express = require('express');
const client = require('prom-client');

const SERVICE_NAME = 'golden-node-express';

const helloHits = new client.Counter({
  name: 'golden_hello_requests_total',
  help: 'Calls to the demo /hello endpoint',
});

// createApp returns the wired app WITHOUT listening — shared by the server bootstrap and the tests,
// so the tests exercise the real routes over supertest without binding a port.
function createApp() {
  const app = express();

  app.get('/health', (_req, res) => res.json({ status: 'ok' }));
  app.get('/ready', (_req, res) => res.json({ status: 'ready' }));

  app.get('/hello', (_req, res) => {
    helloHits.inc();
    res.json({ service: SERVICE_NAME, message: 'hello, weyland' });
  });

  app.get('/metrics', async (_req, res) => {
    res.set('Content-Type', client.register.contentType);
    res.end(await client.register.metrics());
  });

  return app;
}

module.exports = { createApp, SERVICE_NAME };
