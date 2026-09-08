// Astro endpoint — GET /ready (the SMOKE-gate probe).
export const GET = () =>
  new Response(JSON.stringify({ status: 'ready' }), { headers: { 'Content-Type': 'application/json' } });
