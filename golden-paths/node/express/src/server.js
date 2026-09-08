// Bootstrap: bind 0.0.0.0:8080 so the container is reachable in-cluster. Not exercised by the unit
// tests (they use supertest against createApp()), so it is excluded from coverage.
'use strict';

const { createApp, SERVICE_NAME } = require('./app');

createApp().listen(8080, '0.0.0.0', () => {
  console.log(`${SERVICE_NAME} listening on :8080`);
});
