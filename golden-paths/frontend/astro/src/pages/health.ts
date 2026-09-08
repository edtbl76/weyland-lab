// Astro endpoint — GET /health.
export const GET = () =>
  new Response(JSON.stringify({ status: 'ok' }), { headers: { 'Content-Type': 'application/json' } });
