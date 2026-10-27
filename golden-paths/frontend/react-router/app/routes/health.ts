// Resource route — GET /health (a loader with no default export). React Router dropped Remix's json() helper; the
// standard Response.json() replaces it (Remix's server runtime had no static .json(), which is why json() existed).
export const loader = () => Response.json({ status: 'ok' });
