// tracing — deep contract v2 C11, framework-neutral (B262): an OTel span per HTTP request when
// OTEL_EXPORTER_OTLP_ENDPOINT is set (or an exporter is given); a documented no-op otherwise.
//
// One matched OTel JS set (owner-approved 2026-11-27; bump them together): @opentelemetry/api 1.10.0, sdk-trace,
// context-async-hooks and resources 3.1.1, exporter-trace-otlp-http, instrumentation and instrumentation-http 0.301.2.
// The http instrumentation wraps Node's own http server, so it gives every framework (Express, Fastify, Nest) the same
// server span. Call setupTracing() BEFORE the framework is required: instrumentation patches modules as they load.
//
// SOURCE: golden-paths-shared/node/. Each path holds a synced copy (scripts/sync-golden-shared.sh).
'use strict';

/**
 * Starts tracing; returns {provider, shutdown} or null when tracing is off. `exporter` (tests) replaces OTLP/HTTP and
 * exports each span as it ends.
 * @param {{ serviceName?: string, exporter?: object, env?: Record<string, string | undefined> }} [options]
 */
function setupTracing({ serviceName, exporter, env = process.env } = {}) {
  if (!exporter && !env.OTEL_EXPORTER_OTLP_ENDPOINT) return null;
  const { context, trace } = require('@opentelemetry/api');
  const { AsyncLocalStorageContextManager } = require('@opentelemetry/context-async-hooks');
  const { resourceFromAttributes } = require('@opentelemetry/resources');
  const { TracerProvider, BatchSpanProcessor, SimpleSpanProcessor } = require('@opentelemetry/sdk-trace');
  const { registerInstrumentations } = require('@opentelemetry/instrumentation');
  const { HttpInstrumentation } = require('@opentelemetry/instrumentation-http');

  let processor;
  if (exporter) {
    processor = new SimpleSpanProcessor({ exporter });   // 3.x: processors take an options object
  } else {
    const { OTLPTraceExporter } = require('@opentelemetry/exporter-trace-otlp-http');
    processor = new BatchSpanProcessor({ exporter: new OTLPTraceExporter() });   // reads OTEL_EXPORTER_OTLP_ENDPOINT itself
  }
  const provider = new TracerProvider({
    resource: resourceFromAttributes({ 'service.name': serviceName }),
    spanProcessors: [processor],
  });
  const contextManager = new AsyncLocalStorageContextManager().enable();
  context.setGlobalContextManager(contextManager);
  trace.setGlobalTracerProvider(provider);
  const unregister = registerInstrumentations({ tracerProvider: provider, instrumentations: [new HttpInstrumentation()] });
  return {
    provider,
    async shutdown() {
      unregister();
      await provider.shutdown();
      trace.disable();
      context.disable();
    },
  };
}

module.exports = { setupTracing };
