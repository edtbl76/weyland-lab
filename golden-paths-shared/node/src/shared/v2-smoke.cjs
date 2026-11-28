// v2-smoke — the deep contract v2 smoke sequence, framework-neutral (B262; the Node twin of the Python v2_smoke.py).
//
// A path's .smoke runs `node src/shared/v2-smoke.cjs <server command...>`: it starts the server, waits for /ready, then
// runs /hello, create -> get -> list -> 404 envelope -> 422 envelope -> X-Request-ID echo. Built-ins only (fetch,
// child_process), so it needs nothing beyond the image. Exit 0 every step held, or 1 with the first failing step.
//
// .cjs, not .js: this is CommonJS (Node, TypeScript and Sonar then agree it has no top-level await; S7785).
//
// SOURCE: golden-paths-shared/node/. Each path holds a synced copy (scripts/sync-golden-shared.sh).
'use strict';

const { spawn } = require('node:child_process');

const BASE = `http://127.0.0.1:${process.env.PORT || 8080}`;

/** {status, headers, body} for any status: a 4xx is an answer here, not an exception. */
async function call(method, path, body, headers = {}) {
  const res = await fetch(BASE + path, {
    method, headers: { 'Content-Type': 'application/json', ...headers },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(5000),
  });
  const text = await res.text();
  let parsed = null;
  try { parsed = JSON.parse(text); } catch { parsed = text; }
  return { status: res.status, headers: res.headers, body: parsed };
}

async function waitReady(server) {
  for (let i = 0; i < 60; i += 1) {                     // up to ~30s for the server to come up
    if (server.exitCode !== null) return 'server exited during startup';
    try {
      if ((await call('GET', '/ready')).status === 200) return null;
    } catch { /* not listening yet */ }
    await new Promise((r) => setTimeout(r, 500));
  }
  return '/ready never became ready';
}

const show = (r) => `${r.status} ${JSON.stringify(r.body)}`;

/** The deep contract v2 smoke: the first failing step, or null when every step holds. */
async function v2Sequence() {
  const hello = await call('GET', '/hello');
  if (hello.status !== 200 || hello.body.message !== 'hello, weyland') return `/hello returned ${show(hello)}`;
  const made = await call('POST', '/items', { name: 'smoke', tags: ['v2'] });
  if (made.status !== 201 || made.body.name !== 'smoke') return `create returned ${show(made)}`;
  const item = made.body;
  const got = await call('GET', `/items/${item.id}`);
  if (got.status !== 200 || JSON.stringify(got.body) !== JSON.stringify(item)) return `get returned ${show(got)}`;
  const page = await call('GET', '/items?limit=100');
  if (page.status !== 200 || !(page.body.items || []).some((i) => i.id === item.id)) return `list returned ${show(page)}`;
  const missing = await call('GET', '/items/999999999');
  if (missing.status !== 404 || missing.body?.error?.code !== 'not_found') return `unknown item returned ${show(missing)}`;
  const invalid = await call('POST', '/items', { name: '' });
  if (invalid.status !== 422 || invalid.body?.error?.code !== 'validation_failed') {
    return `invalid body returned ${show(invalid)}`;
  }
  const echoed = await call('GET', '/health', undefined, { 'X-Request-ID': 'smoke-rid' });
  if (echoed.headers.get('x-request-id') !== 'smoke-rid') {
    return `X-Request-ID was not echoed (got ${echoed.headers.get('x-request-id')})`;
  }
  return null;
}

/** Start the server with `command`, run the v2 sequence against it, stop it; the exit code. */
async function run(command) {
  const server = spawn(command[0], command.slice(1), { stdio: 'inherit' });
  try {
    const problem = (await waitReady(server)) || (await v2Sequence());
    if (problem) {
      console.error(`SMOKE FAIL: ${problem}`);
      return 1;
    }
    console.log('SMOKE OK: image serves — /ready, /hello and the deep contract v2 sequence');
    return 0;
  } catch (err) {
    console.error(`SMOKE FAIL: ${err.message}`);
    return 1;
  } finally {
    server.kill('SIGTERM');
  }
}

/** The CLI: sets the exit code itself (run() never rejects), so nothing is chained on it. */
async function main(command) {
  if (command.length === 0) {
    console.error('usage: node v2-smoke.cjs <server command...>');
    process.exitCode = 2;
    return;
  }
  process.exitCode = await run(command);
}

if (require.main === module) void main(process.argv.slice(2));   // CommonJS: no top-level await

module.exports = { run, v2Sequence, main };
