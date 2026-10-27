// Resource route — GET /ready (the SMOKE-gate probe).
export const loader = () => Response.json({ status: 'ready' });
