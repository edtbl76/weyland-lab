// Astro endpoint — GET /hello. Increments the demo counter, returns the known payload.
import { greeting } from '../lib/greeting';
import { helloHits } from '../lib/metrics';

export const GET = () => {
  helloHits.inc();
  return new Response(JSON.stringify(greeting()), { headers: { 'Content-Type': 'application/json' } });
};
