/// <reference types="vite/client" />

// Lets plain `tsc --noEmit` (the scan lane) resolve `*.vue` imports — vue-tsc understands SFCs, tsc
// does not, so this shim gives them a generic component type.
declare module '*.vue' {
  import type { DefineComponent } from 'vue';
  const component: DefineComponent<Record<string, unknown>, Record<string, unknown>, unknown>;
  export default component;
}
