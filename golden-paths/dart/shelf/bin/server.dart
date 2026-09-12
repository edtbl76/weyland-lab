// Golden path — server-side Dart / shelf (B160). Binds 0.0.0.0:8080 and serves the contract mux.
import 'dart:io';

import 'package:shelf/shelf_io.dart' as shelf_io;

import 'package:golden_dart_shelf/router.dart';

Future<void> main() async {
  final server = await shelf_io.serve(
    buildRouter(),
    InternetAddress.anyIPv4,
    8080,
  );
  server.autoCompress = true;
  stdout.writeln('{"service":"$serviceName","msg":"listening on :${server.port}"}');
}
