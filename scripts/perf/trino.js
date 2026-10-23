// B104 — Trino perf baseline (k6). Trino's HTTP protocol is submit-then-poll: POST /v1/statement with
// the SQL, then GET each `nextUri` until the query completes. One k6 ITERATION = one full query, so the
// baseline reports queries/s (iterations) + full-query latency (iteration_duration), not per-HTTP-hop.
// Deliberately `SELECT 1` at low VUs — Trino's 4-6Gi heap has an OOM history; never point this at heavy
// aggregations. Env: BASE (default https://trino.data-mesh.svc.cluster.local:8443) · SQL · VUS · DURATION ·
// TRINO_USER / TRINO_PASSWORD (B233: Trino authenticates, over HTTPS only; the Job takes them from the trino-perf
// Secret and trusts the lab CA through SSL_CERT_FILE, which k6, a Go binary, reads for its roots).
import http from 'k6/http';
import encoding from 'k6/encoding';
import { check } from 'k6';

const BASE = __ENV.BASE || 'https://trino.data-mesh.svc.cluster.local:8443';
const SQL = __ENV.SQL || 'SELECT 1';
if (!__ENV.TRINO_USER || !__ENV.TRINO_PASSWORD) {
  throw new Error('TRINO_USER / TRINO_PASSWORD are not set: Trino takes a password only (B233)');
}
const CREDENTIALS = `${__ENV.TRINO_USER}:${__ENV.TRINO_PASSWORD}`;
const AUTH = { Authorization: 'Basic ' + encoding.b64encode(CREDENTIALS) };

export const options = {
  scenarios: {
    trino: {
      executor: 'constant-vus',
      vus: parseInt(__ENV.VUS || '3', 10),
      duration: __ENV.DURATION || '20s',
    },
  },
  summaryTrendStats: ['avg', 'p(50)', 'p(95)', 'p(99)', 'max'],
  thresholds: {},
};

export default function () {
  let res = http.post(`${BASE}/v1/statement`, SQL, {
    headers: { ...AUTH, 'Content-Type': 'text/plain' },
  });
  if (!check(res, { 'submit 200': (r) => r.status === 200 })) return;
  let body = res.json();
  let guard = 0;
  while (body && body.nextUri && guard < 100) {
    res = http.get(body.nextUri, { headers: AUTH });   // every poll is a request, so every poll authenticates
    if (res.status !== 200) break;
    body = res.json();
    guard += 1;
  }
}

export function handleSummary(data) {
  const it = data.metrics.iteration_duration.values;
  const iters = data.metrics.iterations.values;
  const reqs = data.metrics.http_reqs.values.count;
  const failed = data.metrics.http_req_failed ? data.metrics.http_req_failed.values.rate : 0;
  // PERFLINE: queries/s (iterations) · full-query p50/p95/p99 (ms) · err% · total HTTP hops
  const line =
    `PERFLINE ${iters.rate.toFixed(1)} ${it['p(50)'].toFixed(1)} ${it['p(95)'].toFixed(1)} ` +
    `${it['p(99)'].toFixed(1)} ${(failed * 100).toFixed(2)} ${reqs}\n`;
  return { stdout: line };
}
