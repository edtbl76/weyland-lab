// Flat config (eslint 9+) WITH the TypeScript parser.
//
// Plain eslint cannot parse TypeScript: it fails on the first type annotation with
// "Parsing error: Unexpected token :". A TypeScript lint lane that cannot read TypeScript is not a
// lane, so typescript-eslint's parser is load-bearing here, not decoration.
import tseslint from "typescript-eslint";

export default [
  { ignores: ["node_modules/**", "selfcheck/**", "eslint.config.js"] },
  ...tseslint.configs.recommended,
  { rules: { "no-unused-vars": "off", "@typescript-eslint/no-unused-vars": "warn" } },
];
