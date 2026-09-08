// Golden path — Frontend / Astro (B153). The shared greeting the demo page renders and the endpoints
// + lane tests assert. Keeping it in one module is what lets the jest lane test the contract payload
// without rendering an .astro component (which jest cannot transform).
export const SERVICE_NAME = 'golden-frontend-astro';

export function greeting() {
  return { service: SERVICE_NAME, message: 'hello, weyland' };
}
