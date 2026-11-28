// Bootstrap: tracing first (C11: the http instrumentation must patch Node's http before Fastify loads), then bind
// 0.0.0.0:$PORT (default 8080; 0 picks a free port, logged), open the store and drain on SIGTERM (C8). Unit tests
// exercise build() and serve(); test/tracing.test.js runs this file itself.
'use strict';

const { setupTracing } = require('./shared/tracing');

const tracing = setupTracing({ serviceName: 'golden-node-fastify' });
const { build, serve, SERVICE_NAME } = require('./app');

(async () => {
  let store;
  if (process.env.GOLDEN_DATABASE_URL) store = require('./shared/items-backends').buildStoreFromEnv();
  const app = build({ store });
  const { port, shutdown } = await serve(app, { port: Number(process.env.PORT || 8080), host: '0.0.0.0' });
  console.log(JSON.stringify({ event: 'started', service: SERVICE_NAME, port }));
  process.once('SIGTERM', async () => {
    await shutdown();
    if (tracing) await tracing.shutdown();
    process.exit(0);
  });
})().catch((err) => {
  console.error(`${SERVICE_NAME} failed to start: ${err.message}`);
  process.exit(1);
});
