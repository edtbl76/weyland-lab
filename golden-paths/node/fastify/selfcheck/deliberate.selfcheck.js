// selfcheck: the golden-path node lane must SURFACE this failure (exit non-zero). Named *.selfcheck.js
// so `node --test`'s default *.test.* discovery never collects it; run only via --self-check.
'use strict';

const { test } = require('node:test');

test('deliberate failure — the runner must propagate it', () => {
  throw new Error('selfcheck: this failure must reach the lane as a non-zero exit');
});
