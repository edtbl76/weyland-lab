// Golden path — Node / Fastify (B153). Runnable, ephemeral, extendable. Conforms to the golden-path
// contract (docs/design/golden-paths.md): GET /health /ready /metrics /hello.
// Scaffold FROM it: scripts/new-service.sh node/fastify <your-service>.
'use strict';

const Fastify = require('fastify');
const client = require('prom-client');

const SERVICE_NAME = 'golden-node-fastify';

const helloHits = new client.Counter({
  name: 'golden_hello_requests_total',
  help: 'Calls to the demo /hello endpoint',
});

// build returns a Fastify instance WITHOUT listening — the tests drive it via app.inject() (no
// network, no port), which is why this golden path needs no supertest and stays dependency-light.
function build() {
  const app = Fastify({ logger: false });

  app.get('/health', async () => ({ status: 'ok' }));
  app.get('/ready', async () => ({ status: 'ready' }));

  app.get('/hello', async () => {
    helloHits.inc();
    return { service: SERVICE_NAME, message: 'hello, weyland' };
  });

  app.get('/metrics', async (_req, reply) => {
    reply.header('Content-Type', client.register.contentType);
    return client.register.metrics();
  });

  return app;
}

module.exports = { build, SERVICE_NAME };
