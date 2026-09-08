// Golden path — Frontend / Next.js (B153). Shared greeting the demo page renders and the route
// handlers + lane tests assert.
export const SERVICE_NAME = 'golden-frontend-nextjs';

export function greeting() {
  return { service: SERVICE_NAME, message: 'hello, weyland' };
}
