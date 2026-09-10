// selfcheck: the golden-path node lane must SURFACE this failure (exit non-zero). Run only via
// `npm run test:selfcheck` (jest selfcheck); the normal run ignores /selfcheck/.
import { greeting } from '../src/app/greeting';

test('deliberate failure — the runner must propagate it', () => {
  expect(greeting()).toContain('this will not match');
});
