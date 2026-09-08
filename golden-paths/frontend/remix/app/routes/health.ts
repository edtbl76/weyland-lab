// Remix resource route — GET /health (a loader with no default export). Uses Remix's json() helper:
// the server runtime's Response has no static .json().
import { json } from '@remix-run/node';

export const loader = () => json({ status: 'ok' });
