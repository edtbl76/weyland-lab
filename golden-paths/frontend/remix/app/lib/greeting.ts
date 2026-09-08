// Golden path — Frontend / Remix (B153). Shared greeting the demo route renders and the resource
// routes + lane tests assert.
export const SERVICE_NAME = 'golden-frontend-remix';

export function greeting() {
  return { service: SERVICE_NAME, message: 'hello, weyland' };
}
