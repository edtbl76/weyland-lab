// Hello-world fixture for the JavaScript lane (B88). node --test, zero dependencies.
import test from "node:test";
import assert from "node:assert/strict";
import { hello } from "./hello.js";

test("javascript lane executes", () => {
  assert.equal(hello(), "hello, weyland");
});
