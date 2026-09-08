// Next.js route handler — GET /ready (the SMOKE-gate probe).
import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

export function GET() {
  return NextResponse.json({ status: 'ready' });
}
