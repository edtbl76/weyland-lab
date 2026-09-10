// Contract self-test (Angular). Tests the pure greeting logic headlessly with jest — no TestBed, no
// browser (the node lane runs in node:24-alpine). The built Angular app is proven by the curl smoke.
import { greeting, SERVICE } from '../src/app/greeting';

test('greeting returns the demo payload', () => {
  expect(greeting()).toContain('hello, weyland');
});

test('greeting passes a name', () => {
  expect(greeting('mother')).toBe('hello, mother');
});

test('service name is the golden-path id', () => {
  expect(SERVICE).toBe('golden-frontend-angular');
});
