/** @type {import('jest').Config} */
// ts-jest with an explicit commonjs tsconfig for the tests — the Angular tsconfig targets ES2022
// modules, which jest cannot load, and the tests only exercise the pure greeting logic (no Angular
// runtime), so a minimal transform config keeps them independent of the app's build config.
module.exports = {
  testEnvironment: 'node',
  transform: {
    '^.+\\.ts$': [
      'ts-jest',
      { tsconfig: { module: 'commonjs', target: 'ES2020', esModuleInterop: true, strict: true } },
    ],
  },
};
