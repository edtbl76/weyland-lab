// Deliberately-failing test tagged `selfcheck` — proves the flutter lane PROPAGATES failure.
// A normal `flutter test` SKIPS it (dart_test.yaml -> tags.selfcheck.skip -> exit 0); the lane
// self-check runs `flutter test -t selfcheck --run-skipped`, which forces the skip-tagged test to
// actually EXECUTE and exit non-zero. See dart_test.yaml for why --run-skipped is required (the
// same package:test gotcha the sibling dart/shelf golden path documents).
@Tags(['selfcheck'])
library;

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('selfcheck: the golden-path flutter lane must surface this failure', () {
    fail('selfcheck: the golden-path flutter lane must surface this failure (exit non-zero)');
  });
}
