// C11 tracing (NestJS). The http instrumentation must patch Node's http before Nest loads, and jest's module sandbox
// does not route core modules through Node's loader, so spans cannot be observed in-process. The span test compiles
// the app (tsc, as the image does) and runs the REAL bootstrap (dist/main.js) as a child process, exporting over
// OTLP/HTTP to a receiver here.
import http from 'node:http';
import path from 'node:path';
import { execFileSync, spawn } from 'node:child_process';
import { InMemorySpanExporter } from '@opentelemetry/sdk-trace';
import { setupTracing } from '../src/shared/tracing';

const ROOT = path.join(__dirname, '..');

it('C11: no endpoint and no exporter is a no-op', () => {
  expect(setupTracing({ serviceName: 'x', env: {} })).toBeNull();
});

it('C11: with an exporter, tracing starts and shuts down cleanly', async () => {
  const tracing = setupTracing({ serviceName: 'x', exporter: new InMemorySpanExporter(), env: {} })!;
  expect(tracing.provider).toBeDefined();
  await tracing.shutdown();
});

it('C11: an endpoint in the env selects the OTLP/HTTP exporter', async () => {
  const tracing = setupTracing({ serviceName: 'x', env: { OTEL_EXPORTER_OTLP_ENDPOINT: 'http://127.0.0.1:4318' } })!;
  expect(tracing.provider).toBeDefined();
  await tracing.shutdown();                                // nothing was traced, so nothing is sent
});

/** The slice of an OTLP/HTTP JSON trace export this test reads. */
interface OtlpExport {
  resourceSpans: {
    resource: { attributes: { key: string; value: { stringValue?: string } }[] };
    scopeSpans: { spans: { kind: number }[] }[];
  }[];
}

/** An OTLP/HTTP receiver: resolves with the first trace export's JSON body. */
function otlpReceiver(): Promise<{ server: http.Server; exported: Promise<OtlpExport> }> {
  let resolveExport!: (body: OtlpExport) => void;
  const exported = new Promise<OtlpExport>((r) => { resolveExport = r; });
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

const within = <T>(p: Promise<T>, ms: number, what: string) => Promise.race([p, new Promise<never>((_r, reject) => {
  setTimeout(() => reject(new Error(`${what} within ${ms / 1000}s`)), ms).unref();
})]);

it('C11: with OTEL_EXPORTER_OTLP_ENDPOINT set, a request exports a server span over OTLP/HTTP', async () => {
  execFileSync(process.execPath, [require.resolve('typescript/bin/tsc'), '-p', 'tsconfig.build.json'], { cwd: ROOT });
  const { server: receiver, exported } = await otlpReceiver();
  const child = spawn(process.execPath, [path.join(ROOT, 'dist', 'main.js')], {
    env: { ...process.env, PORT: '0', OTEL_EXPORTER_OTLP_ENDPOINT: `http://127.0.0.1:${(receiver.address() as { port: number }).port}` },
    stdio: ['ignore', 'pipe', 'inherit'],
  });
  try {
    const port = await within(new Promise<number>((resolve, reject) => {
      child.stdout!.on('data', (chunk) => {
        const started = String(chunk).split('\n').find((l) => l.includes('"event":"started"'));
        if (started) resolve(JSON.parse(started).port);
      });
      child.once('exit', (code) => reject(new Error(`server exited (${code}) before it started`)));
    }), 15000, 'server did not log "started"');
    expect((await fetch(`http://127.0.0.1:${port}/health`)).status).toBe(200);
    child.kill('SIGTERM');                                 // shutdown flushes the batch processor
    const body = await within(exported, 10000, 'no OTLP trace export arrived');
    const resource = body.resourceSpans[0].resource.attributes;
    expect(resource).toContainEqual({ key: 'service.name', value: { stringValue: 'golden-node-nestjs' } });
    const spans = body.resourceSpans.flatMap((rs) => rs.scopeSpans.flatMap((ss) => ss.spans));
    expect(spans.some((s) => s.kind === 2)).toBe(true);    // OTLP SPAN_KIND_SERVER
  } finally {
    child.kill('SIGKILL');
    receiver.close();
  }
}, 60000);
