// Bootstrap: tracing FIRST (C11: the http instrumentation must patch Node's http before Nest loads; TypeScript hoists
// `import`, so the app is loaded with require after it), then bind 0.0.0.0:$PORT (default 8080; 0 picks a free port,
// logged), open the store and drain on SIGTERM (C8). test/tracing.test.ts runs this file's build.
import { setupTracing } from './shared/tracing';

const tracing = setupTracing({ serviceName: 'golden-node-nestjs' });
// eslint-disable-next-line @typescript-eslint/no-require-imports
const { main } = require('./bootstrap') as typeof import('./bootstrap');

main().then((shutdown) => {
  process.once('SIGTERM', async () => {
    await shutdown();
    if (tracing) await tracing.shutdown();
    process.exit(0);
  });
}).catch((err: Error) => {
  console.error(`golden-node-nestjs failed to start: ${err.message}`);
  process.exit(1);
});
