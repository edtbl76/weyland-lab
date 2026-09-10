// Flat config (eslint 9+) with the TypeScript parser. `.vue` SFCs need vue-eslint-parser, which the
// generic node scan lane does not load, so they are ignored here (advisory linting only); the .ts is
// still linted. A valid config must exist or the scan lane reads "no configuration found" as a finding.
import tseslint from 'typescript-eslint';

export default [
  { ignores: ['node_modules/**', 'coverage/**', 'dist/**', 'build/**', 'selfcheck/**', '**/*.vue'] },
  ...tseslint.configs.recommended,
  { rules: { 'no-unused-vars': 'off', '@typescript-eslint/no-unused-vars': 'warn' } },
];
