// Pure greeting logic — the demo payload, factored out so it is unit-testable with plain jest (no
// Angular TestBed / browser). The AppComponent renders it; the smoke proves the built app serves.
export const SERVICE = 'golden-frontend-angular';

export function greeting(name = 'weyland'): string {
  return `hello, ${name}`;
}
