// Remix resource route — GET /hello. Increments the demo counter, returns the known payload.
import { json } from '@remix-run/node';
import { greeting } from '../lib/greeting';
import { helloHits } from '../lib/metrics';

export const loader = () => {
  helloHits.inc();
  return json(greeting());
};
