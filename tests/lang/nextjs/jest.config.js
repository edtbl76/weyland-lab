// next/jest wires Next's own SWC transform, so this fixture proves the REAL Next.js pipeline
// (JSX + module resolution + next config) rather than a hand-rolled babel setup that would drift
// from what an actual app uses.
const nextJest = require("next/jest");

const createJestConfig = nextJest({ dir: "./" });

module.exports = createJestConfig({
  testEnvironment: "jsdom",
  setupFilesAfterEnv: ["<rootDir>/jest.setup.js"],
});
