// Contract self-test (Astro). jest cannot transform .astro components, so the lane tests the shared
// greeting module + the endpoint handlers directly (they are plain functions returning a Response).
import { greeting, SERVICE_NAME } from '../src/lib/greeting';
import { GET as health } from '../src/pages/health';
import { GET as ready } from '../src/pages/ready';
import { GET as hello } from '../src/pages/hello';
import { GET as metrics } from '../src/pages/metrics';

test('greeting is the known payload', () => {
  expect(greeting()).toEqual({ service: SERVICE_NAME, message: 'hello, weyland' });
});

test('GET /health', async () => {
  const res = health();
  expect(res.status).toBe(200);
  expect(await res.json()).toEqual({ status: 'ok' });
});

test('GET /ready', async () => {
  expect(await ready().json()).toEqual({ status: 'ready' });
});

test('GET /hello returns the known payload', async () => {
  const res = hello();
  expect(await res.json()).toEqual({ service: SERVICE_NAME, message: 'hello, weyland' });
});

test('GET /metrics exposes prometheus', async () => {
  hello();
  const body = await (await metrics()).text();
  expect(body).toContain('golden_hello_requests_total');
});
