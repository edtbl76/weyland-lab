// Flat config (eslint 9+) with the TypeScript parser. Angular HTML templates need angular-eslint, which
// the generic node scan lane does not load, so `.html` is ignored (advisory linting of the .ts only).
// A valid config must exist or the scan lane reads "no configuration found" as a finding.
import tseslint from 'typescript-eslint';

export default [
  { ignores: ['node_modules/**', 'dist/**', '.angular/**', 'coverage/**', 'selfcheck/**', '**/*.html'] },
  ...tseslint.configs.recommended,
  { rules: { 'no-unused-vars': 'off', '@typescript-eslint/no-unused-vars': 'warn' } },
];
