// Run ONLY by `run-lang-tests.sh javascript --self-check`. MUST fail — that is the point.
import test from "node:test";
import assert from "node:assert/strict";

test("deliberate failure (proves the javascript lane can fail)", () => {
  assert.equal("this", "fails");
});
