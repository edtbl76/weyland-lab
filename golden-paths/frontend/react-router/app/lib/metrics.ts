// One shared prom-client counter + registry so /hello (increments) and /metrics (scrapes) agree.
import client from 'prom-client';

export const helloHits = new client.Counter({
  name: 'golden_hello_requests_total',
  help: 'Calls to the demo /hello endpoint',
});

export const registry = client.register;
