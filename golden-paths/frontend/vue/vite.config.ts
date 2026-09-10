/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  plugins: [vue()],
  build: { outDir: 'dist' },
  test: { environment: 'jsdom' },
});
