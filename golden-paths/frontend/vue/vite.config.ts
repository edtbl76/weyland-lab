/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  plugins: [vue()],
  build: { outDir: 'dist' },
  // `npm test -- --coverage` (the coverage-ratchet's cov_node) needs a provider + the istanbul-style
  // `text` reporter, whose "All files" row the ratchet parses. Without this vitest emits no figure and
  // the ratchet fails closed ("no coverage figure"). include=src so the demo component is measured.
  test: {
    environment: 'jsdom',
    coverage: { provider: 'v8', reporter: ['text'], include: ['src/**'], exclude: ['src/main.ts'] },
  },
});
