// Golden path — Node / NestJS (B153; deep contract v2 since B262). Runnable, ephemeral, extendable.
//
// The minimal contract (docs/design/golden-paths.md): GET /health /ready /metrics /hello.
// Deep contract v2 (docs/concepts/golden-path-capabilities.md), each row in Nest's own idiom:
//   C1 routing      GET /items?limit&offset, GET /items/:id, POST /items (items.controller.ts)
//   C2 validation   class-validator DTOs + the global ValidationPipe; a bad request is 422 with per-field errors
//   C3 errors       one envelope {"error": {code, message, request_id}} from a catch-all exception filter (errors.ts)
//   C4 middleware   X-Request-ID + one JSON access-log line per request (request-context.middleware.ts)
//   C5 metrics      http_requests_total{route,status} + http_request_duration_seconds{route}, per route template
//   C6 config       the SETTINGS provider: loadSettings() validates GOLDEN_GREETING when the app is built
//   C7 DI           modules / providers: ITEM_STORE, in-memory by default (AppModule.forRoot)
//   C8 lifecycle    Lifecycle.start() after listen flips /ready; OnApplicationShutdown closes the store
//   C9 tests        @nestjs/testing + supertest, one test per row (test/app.test.ts)
//   C10 OpenAPI     @nestjs/swagger, native: /openapi.json
//   C11 tracing     setupTracing() (src/shared/tracing.js), started by main.ts before Nest loads
//
// Scaffold FROM it: scripts/new-service.sh node/nestjs <your-service>.
import { Controller, Get, Header, Inject } from '@nestjs/common';
import { ApiExcludeEndpoint } from '@nestjs/swagger';
import * as client from 'prom-client';
import { ApiError } from './errors';
import { Lifecycle } from './lifecycle';
import { SETTINGS } from './tokens';

// The one place a scaffolded service is renamed (scripts/new-service.sh rewrites this token).
export const SERVICE_NAME = 'golden-node-nestjs';

const helloHits = new client.Counter({ name: 'golden_hello_requests_total', help: 'Calls to the demo /hello endpoint' });

@Controller()
export class AppController {
  constructor(@Inject(SETTINGS) private readonly settings: { greeting: string }, private readonly lifecycle: Lifecycle) {}

  @Get('/health')
  health() {
    return { status: 'ok' };
  }

  @Get('/ready')
  ready() {
    if (!this.lifecycle.ready) throw new ApiError(503, 'not_ready', 'the service is starting');
    return { status: 'ready' };
  }

  @Get('/hello')
  hello() {
    helloHits.inc();
    return { service: SERVICE_NAME, message: this.settings.greeting };
  }

  @Get('/metrics')
  @ApiExcludeEndpoint()
  @Header('Content-Type', client.register.contentType)
  metrics(): Promise<string> {
    return client.register.metrics();
  }
}
