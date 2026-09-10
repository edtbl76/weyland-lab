// selfcheck: the golden-path node lane must SURFACE this failure (exit non-zero). Run only via
// `npm run test:selfcheck` (vitest --dir selfcheck); the normal run scans --dir test and never sees it.
import { mount } from '@vue/test-utils';
import { describe, it, expect } from 'vitest';
import Hello from '../src/Hello.vue';

describe('selfcheck', () => {
  it('deliberate failure — the runner must propagate it', () => {
    expect(mount(Hello).text()).toContain('this will not match');
  });
});
