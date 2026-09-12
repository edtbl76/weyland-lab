// Widget test — the mobile-contract self-test. Renders the app and asserts the known payload
// `hello, weyland` is on screen. This is what a normal `flutter test` runs (and passes); the
// deliberately-failing selfcheck (test/selfcheck_test.dart, tagged `selfcheck`) is skipped here.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:golden_flutter/main.dart';

void main() {
  testWidgets('renders the known payload "hello, weyland"', (WidgetTester tester) async {
    await tester.pumpWidget(const GoldenFlutterApp());

    // Assert the greeting renders — by text and by its stable Key.
    expect(find.text('hello, weyland'), findsOneWidget);
    expect(find.byKey(const Key('greeting')), findsOneWidget);
  });

  testWidgets('the greeting matches the exported payload constant', (WidgetTester tester) async {
    await tester.pumpWidget(const GoldenFlutterApp());
    expect(find.text(greeting), findsOneWidget);
    expect(greeting, equals('hello, weyland'));
  });

  test('the service-name token is the golden-path scaffolder placeholder', () {
    expect(serviceName, equals('golden-flutter'));
  });
}
