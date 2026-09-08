// Minimal flat config (eslint 9+) for the SCAN lane. A golden path must lint clean, and the scan
// lane needs a valid config or eslint exits "no configuration found" and reads as a finding.
export default [
  { ignores: ['node_modules/**', 'coverage/**', 'dist/**', 'selfcheck/**'] },
  { files: ['**/*.{js,mjs}'], rules: { 'no-unused-vars': 'warn' } },
];
