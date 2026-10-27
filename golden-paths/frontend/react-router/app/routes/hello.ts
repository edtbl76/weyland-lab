// Resource route — GET /hello. Increments the demo counter, returns the known payload.
import { greeting } from '../lib/greeting';
import { helloHits } from '../lib/metrics';

export const loader = () => {
  helloHits.inc();
  return Response.json(greeting());
};
