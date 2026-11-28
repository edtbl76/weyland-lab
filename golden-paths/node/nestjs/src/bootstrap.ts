// The app factory and the server (C8), separate from main.ts so main.ts can start tracing (C11) before any of Nest
// is loaded. createApp() is what the tests drive; serve() is what main.ts runs.
import { INestApplication, ValidationPipe } from '@nestjs/common';
import { NestFactory } from '@nestjs/core';
import type { NestExpressApplication } from '@nestjs/platform-express';
import type { NextFunction, Request, Response } from 'express';
import { DocumentBuilder, SwaggerModule } from '@nestjs/swagger';
import { AppModule, AppOptions } from './app.module';
import { SERVICE_NAME } from './app.controller';
import { ApiError, EnvelopeFilter, validationFailed } from './errors';
import { Lifecycle } from './lifecycle';
import { RequestContextMiddleware } from './request-context.middleware';

// express.json() fails a malformed body with type entity.parse.failed; Nest would map that SyntaxError to a bare
// 400, so it becomes the contract's 422 here, before Nest sees it.
function malformedBodyIs422(err: { type?: string }, _req: Request, _res: Response, next: NextFunction) {
  next(err?.type === 'entity.parse.failed'
    ? new ApiError(422, 'validation_failed', 'the request is invalid', [{ field: 'body', message: 'malformed JSON' }])
    : err);
}

/** The configured application, initialised but not listening (and the store not yet open). */
export async function createApp(options: AppOptions = {}): Promise<INestApplication> {
  // abortOnError false: a startup error (an invalid GOLDEN_GREETING, C6) is thrown to the caller, not process.exit(1).
  // bodyParser false: the request context (C4) runs FIRST, so even a request whose body fails to parse gets its
  // X-Request-ID and its access-log line; then Nest's JSON parser, then the malformed-body translation.
  const app = await NestFactory.create<NestExpressApplication>(AppModule.forRoot(options),
    { logger: false, abortOnError: false, bodyParser: false });
  const context = app.get(RequestContextMiddleware);
  app.use(context.use.bind(context));
  app.useBodyParser('json');
  app.use(malformedBodyIs422);
  app.useGlobalPipes(new ValidationPipe({ transform: true, whitelist: true, exceptionFactory: validationFailed }));
  app.useGlobalFilters(app.get(EnvelopeFilter));
  // No enableShutdownHooks(): Nest's signal handler re-raises SIGTERM after close, killing the process before tracing
  // flushes. main.ts owns the signal; app.close() runs OnApplicationShutdown either way.
  // C10: the OpenAPI document, native, at /openapi.json (no UI: a template serves its contract, not a console)
  const document = SwaggerModule.createDocument(app, new DocumentBuilder().setTitle(SERVICE_NAME).setVersion('2.0.0').build());
  SwaggerModule.setup('docs', app, document, { ui: false, raw: ['json'], jsonDocumentUrl: 'openapi.json' });
  await app.init();
  return app;
}

/** Listen, then open the store and flip /ready. shutdown() is app.close(): drain, then OnApplicationShutdown. */
export async function serve(app: INestApplication, { port = 8080, host = '0.0.0.0' } = {}) {
  await app.listen(port, host);
  await app.get(Lifecycle).start();
  return { port: app.getHttpServer().address().port as number, shutdown: () => app.close() };
}

export async function main() {
  let store;
  if (process.env.GOLDEN_DATABASE_URL) store = (await import('./shared/items-backends')).buildStoreFromEnv();
  const app = await createApp({ store });
  const { port, shutdown } = await serve(app, { port: Number(process.env.PORT || 8080) });
  console.log(JSON.stringify({ event: 'started', service: SERVICE_NAME, port }));
  return shutdown;
}
