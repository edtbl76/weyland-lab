// ESLint flat config (2026-10-27). Next.js 16 removed `next lint` and eslint-config-next 16 needs ESLint 9, so the
// Next rule set that `.eslintrc.json` ("extends": "next/core-web-vitals") pulled in is imported here instead, and the
// scan lane's plain `eslint .` step runs it. The ignores replace `.eslintignore`.
import nextCoreWebVitals from "eslint-config-next/core-web-vitals";

export default [
  ...nextCoreWebVitals,
  { ignores: ["node_modules/**", ".next/**", "next-env.d.ts"] },
];
