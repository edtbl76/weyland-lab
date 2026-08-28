// Minimal flat config (eslint 9+). A fixture whose job is proving the SCAN lane runs needs a valid
// config, or eslint exits 2 "no configuration found" and that reads as a finding rather than a
// missing setup.
export default [
  {
    files: ["**/*.{js,ts}"],
    ignores: ["node_modules/**", "selfcheck/**"],
    rules: { "no-unused-vars": "warn" },
  },
];
