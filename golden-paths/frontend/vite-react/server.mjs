// Tiny static server for the built SPA — the "sidecar route" the adapted frontend contract allows.
// Serves dist/ (SPA fallback to index.html) AND the contract endpoints /health /ready /metrics /hello.
// Stdlib http only + prom-client; no express, no framework runtime.
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { join, extname, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';
import client from 'prom-client';

const SERVICE_NAME = 'golden-frontend-vite-react';
const DIST = fileURLToPath(new URL('./dist/', import.meta.url));

const helloHits = new client.Counter({
  name: 'golden_hello_requests_total',
  help: 'Calls to the demo /hello endpoint',
});

const TYPES = {
  '.html': 'text/html',
  '.js': 'text/javascript',
  '.css': 'text/css',
  '.svg': 'image/svg+xml',
  '.json': 'application/json',
  '.ico': 'image/x-icon',
};

const sendJson = (res, obj) => {
  res.writeHead(200, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(obj));
};

const server = createServer(async (req, res) => {
  const url = (req.url || '/').split('?')[0];

  if (url === '/health') return sendJson(res, { status: 'ok' });
  if (url === '/ready') return sendJson(res, { status: 'ready' });
  if (url === '/hello') {
    helloHits.inc();
    return sendJson(res, { service: SERVICE_NAME, message: 'hello, weyland' });
  }
  if (url === '/metrics') {
    res.writeHead(200, { 'Content-Type': client.register.contentType });
    return res.end(await client.register.metrics());
  }

  // Static assets, with an SPA fallback to index.html. normalize + the DIST prefix check keep a
  // crafted `..` path from escaping the build directory.
  const rel = url === '/' ? 'index.html' : url.replace(/^\/+/, '');
  const file = join(DIST, normalize(rel));
  if (!file.startsWith(DIST)) {
    res.writeHead(403);
    return res.end('forbidden');
  }
  try {
    const body = await readFile(file);
    res.writeHead(200, { 'Content-Type': TYPES[extname(file)] || 'application/octet-stream' });
    res.end(body);
  } catch {
    res.writeHead(200, { 'Content-Type': 'text/html' });
    res.end(await readFile(join(DIST, 'index.html')));
  }
});

server.listen(8080, '0.0.0.0', () => {
  // eslint-disable-next-line no-console
  console.log(`${SERVICE_NAME} listening on :8080`);
});
