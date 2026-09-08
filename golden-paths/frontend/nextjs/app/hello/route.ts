// Next.js route handler — GET /hello. Increments the demo counter, returns the known payload.
import { NextResponse } from 'next/server';
import { greeting } from '../../lib/greeting';
import { helloHits } from '../../lib/metrics';

export const dynamic = 'force-dynamic';

export function GET() {
  helloHits.inc();
  return NextResponse.json(greeting());
}
