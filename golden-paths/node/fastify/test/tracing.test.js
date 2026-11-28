// C11 tracing (Fastify). The http instrumentation must patch Node's http before Fastify loads (it patches modules as
// they load), so the span test runs the REAL bootstrap (src/server.js) as a child process, exporting over OTLP/HTTP to
// a receiver here.
'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { InMemorySpanExporter } = require('@opentelemetry/sdk-trace');
const { setupTracing } = require('../src/shared/tracing');

test('C11: no endpoint and no exporter is a no-op', () => {
  assert.equal(setupTracing({ serviceName: 'x', env: {} }), null);
});

test('C11: with an exporter, tracing starts and shuts down cleanly', async () => {
  const tracing = setupTracing({ serviceName: 'x', exporter: new InMemorySpanExporter(), env: {} });
  assert.ok(tracing.provider);
  await tracing.shutdown();
});

test('C11: an endpoint in the env selects the OTLP/HTTP exporter', async () => {
  const tracing = setupTracing({ serviceName: 'x', env: { OTEL_EXPORTER_OTLP_ENDPOINT: 'http://127.0.0.1:4318' } });
  assert.ok(tracing.provider);
  await tracing.shutdown();                                // nothing was traced, so nothing is sent
});

/** An OTLP/HTTP receiver: resolves with the first trace export's JSON body. */
function otlpReceiver() {
  let resolveExport;
  const exported = new Promise((r) => { resolveExport = r; });
  const server = http.createServer((req, res) => {
    let body = '';
    req.on('data', (c) => { body += c; });
    req.on('end', () => {
      res.writeHead(200, { 'Content-Type': 'application/json' }).end('{}');
      if (req.url === '/v1/traces') resolveExport(JSON.parse(body));
    });
  });
  return new Promise((r) => server.listen(0, '127.0.0.1', () => r({ server, exported })));
}

test('C11: with OTEL_EXPORTER_OTLP_ENDPOINT set, a request exports a server span over OTLP/HTTP', { timeout: 20000 }, async () => {
  const { server: receiver, exported } = await otlpReceiver();
  const child = spawn(process.execPath, [path.join(__dirname, '..', 'src', 'server.js')], {
    env: { ...process.env, PORT: '0', OTEL_EXPORTER_OTLP_ENDPOINT: `http://127.0.0.1:${receiver.address().port}` },
    stdio: ['ignore', 'pipe', 'inherit'],
  });
  try {
    const port = await new Promise((resolve, reject) => {
      // a deadline, so a server that never starts fails this test instead of hanging it (finally kills the child)
      setTimeout(() => reject(new Error('server did not log "started" within 10s')), 10000).unref();
      child.stdout.on('data', (chunk) => {
        const started = String(chunk).split('\n').find((l) => l.includes('"event":"started"'));
        if (started) resolve(JSON.parse(started).port);
      });
      child.once('exit', (code) => reject(new Error(`server exited (${code}) before it started`)));
    });
    assert.equal((await fetch(`http://127.0.0.1:${port}/health`)).status, 200);
    child.kill('SIGTERM');                                 // shutdown flushes the batch processor
    const body = await Promise.race([exported, new Promise((_r, reject) => {
      setTimeout(() => reject(new Error('no OTLP trace export arrived within 10s')), 10000).unref();
    })]);
    const resource = body.resourceSpans[0].resource.attributes;
    assert.ok(resource.some((a) => a.key === 'service.name' && a.value.stringValue === 'golden-node-fastify'));
    const spans = body.resourceSpans.flatMap((rs) => rs.scopeSpans.flatMap((ss) => ss.spans));
    assert.ok(spans.some((s) => s.kind === 2));    // OTLP SPAN_KIND_SERVER
  } finally {
    child.kill('SIGKILL');
    receiver.close();
  }
});
