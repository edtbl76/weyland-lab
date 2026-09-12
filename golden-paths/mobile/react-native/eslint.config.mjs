// Flat config (eslint 9+) WITH the TypeScript parser — plain eslint cannot parse TS/TSX. A golden path
// must lint clean; the scan lane needs a valid config or eslint reads "no configuration found" as a
// finding. Mirrors the estate's blessed TS lint setup (frontend/vite-react). React Native globals are
// declared so the RN/JSX source lints without `no-undef` noise.
import tseslint from 'typescript-eslint';

export default [
  {
    ignores: [
      'node_modules/**',
      'dist/**',
      'build/**',
      '.expo/**',
      'web-build/**',
      'coverage/**',
      'selfcheck/**',
      'babel.config.js',
    ],
  },
  ...tseslint.configs.recommended,
  {
    languageOptions: {
      globals: { __DEV__: 'readonly', process: 'readonly' },
    },
    rules: {
      'no-unused-vars': 'off',
      '@typescript-eslint/no-unused-vars': 'warn',
    },
  },
];
