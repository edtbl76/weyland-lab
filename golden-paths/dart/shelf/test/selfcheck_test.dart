// Deliberately-failing test tagged `selfcheck` — proves the dart lane PROPAGATES failure.
// A normal `dart test` skips it (dart_test.yaml → tags.selfcheck.skip → exit 0); the lane
// self-check runs `dart test -t selfcheck --run-skipped`, which forces the tagged test to
// actually execute and exit non-zero. See dart_test.yaml for why --run-skipped is required.
@Tags(['selfcheck'])
library;

import 'package:test/test.dart';

void main() {
  test('selfcheck: the golden-path dart lane must surface this failure', () {
    fail('selfcheck: the golden-path dart lane must surface this failure (exit non-zero)');
  });
}
