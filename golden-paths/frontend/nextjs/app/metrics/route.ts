// Next.js route handler — GET /metrics. Prometheus exposition of the shared registry.
import { registry } from '../../lib/metrics';

export const dynamic = 'force-dynamic';

export async function GET() {
  return new Response(await registry.metrics(), { headers: { 'Content-Type': registry.contentType } });
}
