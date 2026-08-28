// Hello-world fixture for the TypeScript lane (B88).
// Runs on node's built-in test runner with native type-stripping — no jest, no vitest, no deps.
import test from "node:test";
import assert from "node:assert/strict";
import { hello } from "./hello.ts";

test("typescript lane executes and types strip", () => {
  assert.equal(hello(), "hello, weyland");
});
