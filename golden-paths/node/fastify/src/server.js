// Bootstrap: bind 0.0.0.0:8080 so the container is reachable in-cluster. Not exercised by the unit
// tests (they use app.inject()), so it is excluded from coverage.
'use strict';

const { build } = require('./app');

build()
  .listen({ port: 8080, host: '0.0.0.0' })
  .catch((err) => {
    // eslint-disable-next-line no-console
    console.error(err);
    process.exit(1);
  });
