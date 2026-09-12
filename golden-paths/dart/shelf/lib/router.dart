// Golden path — server-side Dart / shelf (B160).
//
// The idiomatic shelf + shelf_router baseline. Runnable, ephemeral, extendable. Conforms to the
// golden-path contract (docs/design/golden-paths.md): GET /health /ready /metrics /hello.
// Scaffold FROM it: scripts/new-service.sh dart/shelf <your-service>.
library;

import 'dart:convert';

import 'package:shelf/shelf.dart';
import 'package:shelf_router/shelf_router.dart';

const serviceName = 'golden-dart-shelf';

/// Calls to the demo /hello endpoint. Library-global so it survives across router builds.
int helloHits = 0;

Response _json(Map<String, String> body) => Response.ok(
      jsonEncode(body),
      headers: {'content-type': 'application/json'},
    );

/// Renders a minimal-but-valid Prometheus text exposition (format version 0.0.4).
String _renderMetrics() {
  final buf = StringBuffer()
    ..writeln('# HELP golden_hello_requests_total Calls to the demo /hello endpoint')
    ..writeln('# TYPE golden_hello_requests_total counter')
    ..writeln('golden_hello_requests_total $helloHits');
  return buf.toString();
}

/// Builds the contract handler. Returned as a [Handler] so tests drive it directly
/// (no live socket needed) and `bin/server.dart` serves it over shelf_io.
Handler buildRouter() {
  final router = Router();

  router.get('/health', (Request _) => _json({'status': 'ok'}));
  router.get('/ready', (Request _) => _json({'status': 'ready'}));
  router.get('/hello', (Request _) {
    helloHits++;
    return _json({'service': serviceName, 'message': 'hello, weyland'});
  });
  router.get('/metrics', (Request _) => Response.ok(
        _renderMetrics(),
        headers: {'content-type': 'text/plain; version=0.0.4; charset=utf-8'},
      ));

  return router.call;
}
