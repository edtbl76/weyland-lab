// Golden path — Frontend / React Router (B153; Remix until 2026-10-27). Shared greeting the demo route renders and the resource
// routes + lane tests assert.
export const SERVICE_NAME = 'golden-frontend-react-router';

export function greeting() {
  return { service: SERVICE_NAME, message: 'hello, weyland' };
}
