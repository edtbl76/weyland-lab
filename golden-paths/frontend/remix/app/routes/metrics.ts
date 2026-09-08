// Remix resource route — GET /metrics. Prometheus exposition of the shared registry.
import { registry } from '../lib/metrics';

export const loader = async () =>
  new Response(await registry.metrics(), { headers: { 'Content-Type': registry.contentType } });
