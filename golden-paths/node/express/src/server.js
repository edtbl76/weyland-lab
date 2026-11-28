// Bootstrap: tracing first (C11: the http instrumentation must patch Node's http before Express loads), then bind
// 0.0.0.0:$PORT (default 8080; 0 picks a free port, logged), open the store and drain on SIGTERM (C8). Unit tests
// exercise createApp() and serve(); test/tracing.test.js runs this file itself, so it is excluded from coverage.
'use strict';

const { setupTracing } = require('./shared/tracing');

const tracing = setupTracing({ serviceName: 'golden-node-express' });
const { createApp, serve, SERVICE_NAME } = require('./app');

(async () => {
  let store;
  if (process.env.GOLDEN_DATABASE_URL) store = require('./shared/items-backends').buildStoreFromEnv();
  const app = createApp({ store });
  const port = Number(process.env.PORT || 8080);
  const { server, shutdown } = await serve(app, { port, host: '0.0.0.0' });
  console.log(JSON.stringify({ event: 'started', service: SERVICE_NAME, port: server.address().port }));
  process.once('SIGTERM', async () => {
    await shutdown();
    if (tracing) await tracing.shutdown();
    process.exit(0);
  });
})().catch((err) => {
  console.error(`${SERVICE_NAME} failed to start: ${err.message}`);
  process.exit(1);
});
