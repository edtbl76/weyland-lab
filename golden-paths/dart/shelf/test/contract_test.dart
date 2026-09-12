// Golden-path self-test (Dart/shelf) — the lane probe + contract proof.
// Drives the handler directly (no live socket), mirroring the go exemplar's httptest approach.
import 'dart:convert';

import 'package:shelf/shelf.dart';
import 'package:test/test.dart';

import 'package:golden_dart_shelf/router.dart';

Future<Response> _get(String path) {
  final handler = buildRouter();
  return Future.value(handler(Request('GET', Uri.parse('http://localhost:8080$path'))));
}

void main() {
  test('GET /health returns 200 + status ok', () async {
    final resp = await _get('/health');
    expect(resp.statusCode, 200);
    final body = jsonDecode(await resp.readAsString()) as Map<String, dynamic>;
    expect(body['status'], 'ok');
  });

  test('GET /ready returns 200 + status ready', () async {
    final resp = await _get('/ready');
    expect(resp.statusCode, 200);
    final body = jsonDecode(await resp.readAsString()) as Map<String, dynamic>;
    expect(body['status'], 'ready');
  });

  test('GET /hello returns the known payload', () async {
    final resp = await _get('/hello');
    expect(resp.statusCode, 200);
    final body = jsonDecode(await resp.readAsString()) as Map<String, dynamic>;
    expect(body['service'], serviceName);
    expect(body['message'], 'hello, weyland');
  });

  test('GET /metrics exposes Prometheus text', () async {
    await _get('/hello');
    final resp = await _get('/metrics');
    expect(resp.statusCode, 200);
    final text = await resp.readAsString();
    expect(text, contains('golden_hello_requests_total'));
  });
}
