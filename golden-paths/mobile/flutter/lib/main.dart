// Golden path — MOBILE Flutter client (B164). A cross-platform Flutter CLIENT: it bundles + builds
// and renders a known payload. It exposes NO HTTP endpoints (a mobile app is a client, not a service),
// so there is no /health /ready /metrics /hello, no Dockerfile, and no run-to-completion Job — the
// adapted mobile contract (docs/design/golden-paths.md) is: app builds + widget test + selfcheck +
// headless build smoke.

import 'package:flutter/material.dart';

/// Service-name token for the golden-path scaffolder (mirrors `golden-<lang>-<framework>`).
/// `scripts/new-service.sh mobile/flutter <name>` rewrites this to the real service name.
const String serviceName = 'golden-flutter';

/// The known payload the widget test asserts renders and the build smoke bundles.
const String greeting = 'hello, weyland';

void main() => runApp(const GoldenFlutterApp());

class GoldenFlutterApp extends StatelessWidget {
  const GoldenFlutterApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: serviceName,
      debugShowCheckedModeBanner: false,
      theme: ThemeData(useMaterial3: true, colorSchemeSeed: const Color(0xFF0175C2)),
      home: const GreetingPage(),
    );
  }
}

class GreetingPage extends StatelessWidget {
  const GreetingPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text(serviceName)),
      body: const Center(
        // The widget test finds this by text; the Key is a stable hook for scaffolded services.
        child: Text(greeting, key: Key('greeting')),
      ),
    );
  }
}
