import { defineConfig } from 'astro/config';
import node from '@astrojs/node';

// SSR (output: 'server') so the .ts endpoints and the SSR-rendered demo page are both served by a
// real node server — the standalone adapter honours HOST/PORT (set in the Dockerfile / smoke).
export default defineConfig({
  output: 'server',
  adapter: node({ mode: 'standalone' }),
});
