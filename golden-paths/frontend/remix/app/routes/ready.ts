// Remix resource route — GET /ready (the SMOKE-gate probe).
import { json } from '@remix-run/node';

export const loader = () => json({ status: 'ready' });
