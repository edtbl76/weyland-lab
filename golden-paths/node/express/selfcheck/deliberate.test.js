// selfcheck: the golden-path node lane must SURFACE this failure (exit non-zero). Run only via
// `--self-check` (npm run test:selfcheck); the normal run ignores /selfcheck/.
'use strict';

test('deliberate failure — the runner must propagate it', () => {
  throw new Error('selfcheck: this failure must reach the lane as a non-zero exit');
});
