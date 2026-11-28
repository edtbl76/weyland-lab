// C4 + C5: X-Request-ID (echoed or generated), one JSON access-log line per request, and the per-route metrics, as
// a Nest middleware applied globally (bootstrap.ts, ahead of the body parser). Recorded when the response finishes,
// so unmatched routes, unparseable bodies and errors are counted too (an interceptor runs only for a matched handler).
import { Inject, Injectable, NestMiddleware } from '@nestjs/common';
import { randomUUID } from 'node:crypto';
import type { NextFunction, Request, Response } from 'express';
import * as client from 'prom-client';
import { LOG, LogFn } from './tokens';

const requests = new client.Counter({
  name: 'http_requests_total', help: 'HTTP requests by route template and status', labelNames: ['route', 'status'],
});
const latency = new client.Histogram({
  name: 'http_request_duration_seconds', help: 'HTTP request latency by route template', labelNames: ['route'],
});

@Injectable()
export class RequestContextMiddleware implements NestMiddleware {
  constructor(@Inject(LOG) private readonly log: LogFn) {}

  use(req: Request, res: Response, next: NextFunction) {
    const rid = req.header('x-request-id') || randomUUID().replaceAll('-', '');
    res.setHeader('X-Request-ID', rid);
    const started = process.hrtime.bigint();
    res.on('finish', () => {
      const seconds = Number(process.hrtime.bigint() - started) / 1e9;
      const template = req.route?.path ?? 'unmatched';
      requests.inc({ route: template, status: String(res.statusCode) });
      latency.observe({ route: template }, seconds);
      this.log(JSON.stringify({ method: req.method, path: req.path, status: res.statusCode, request_id: rid,
        duration_ms: Math.round(seconds * 1e6) / 1e3 }));
    });
    next();
  }
}
