// B104 — HTTP perf baseline (k6). Bounded, record-mode load against a service's LIGHT serving-plane
// endpoints (health/models/SELECT 1) — measures the service's own throughput + latency, NOT upstream
// model inference or heavy queries. Driven by scripts/perf-baseline.sh; parameters come from env:
//   BASE      base URL (e.g. http://192.168.1.243:30080)
//   PATHS     comma-separated paths to round-robin (e.g. /health,/ready)
//   VUS       constant virtual users (default 10 — deliberately low; mother is swapless, ~4.6Gi headroom)
//   DURATION  test duration (default 30s)
//   AUTH      optional Authorization header value
import http from 'k6/http';
import { check } from 'k6';

const BASE = __ENV.BASE;
const PATHS = (__ENV.PATHS || '/health').split(',');
const AUTH = __ENV.AUTH || '';

export const options = {
  scenarios: {
    baseline: {
      executor: 'constant-vus',
      vus: parseInt(__ENV.VUS || '10', 10),
      duration: __ENV.DURATION || '30s',
    },
  },
  // Record-mode: report the percentiles, do not gate. A perf regression threshold is added later,
  // once a committed baseline exists to ratchet against.
  summaryTrendStats: ['avg', 'p(50)', 'p(95)', 'p(99)', 'max'],
  thresholds: {},
};

export default function () {
  const path = PATHS[Math.floor(Math.random() * PATHS.length)];
  const params = AUTH ? { headers: { Authorization: AUTH } } : {};
  const res = http.get(`${BASE}${path}`, params);
  check(res, { 'status < 400': (r) => r.status < 400 });
}

export function handleSummary(data) {
  const d = data.metrics.http_req_duration.values;
  const reqs = data.metrics.http_reqs ? data.metrics.http_reqs.values : { rate: 0, count: 0 };
  const failed = data.metrics.http_req_failed ? data.metrics.http_req_failed.values.rate : 0;
  // One machine-parseable line the runner greps: rps p50 p95 p99 err% count
  const line =
    `PERFLINE ${reqs.rate.toFixed(1)} ${d['p(50)'].toFixed(1)} ${d['p(95)'].toFixed(1)} ` +
    `${d['p(99)'].toFixed(1)} ${(failed * 100).toFixed(2)} ${reqs.count}\n`;
  return { stdout: line };
}
