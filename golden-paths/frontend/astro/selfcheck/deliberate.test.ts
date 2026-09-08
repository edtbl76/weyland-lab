// selfcheck: the golden-path node lane must SURFACE this failure (exit non-zero). Run only via
// `--self-check` (npm run test:selfcheck); the normal run ignores /selfcheck/.
import { greeting } from '../src/lib/greeting';

test('deliberate failure — the runner must propagate it', () => {
  expect(greeting().message).toBe('this will not match');
});
