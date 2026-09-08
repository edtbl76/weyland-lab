// Astro endpoint — GET /metrics. Prometheus exposition of the shared registry.
import { registry } from '../lib/metrics';

export const GET = async () =>
  new Response(await registry.metrics(), { headers: { 'Content-Type': registry.contentType } });
