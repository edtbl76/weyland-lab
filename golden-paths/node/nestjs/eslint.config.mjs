// Flat config (eslint 9+) WITH the TypeScript parser — plain eslint cannot parse TS (it fails on the
// first type annotation). A golden path must lint clean; the scan lane needs a valid config or eslint
// reads "no configuration found" as a finding. Mirrors the estate's blessed TS lint setup.
import tseslint from 'typescript-eslint';

export default [
  { ignores: ['node_modules/**', 'coverage/**', 'dist/**', 'build/**', '.next/**', '.astro/**', 'selfcheck/**', '**/*.astro'] },
  ...tseslint.configs.recommended,
  { rules: { 'no-unused-vars': 'off', '@typescript-eslint/no-unused-vars': 'warn' } },
];
