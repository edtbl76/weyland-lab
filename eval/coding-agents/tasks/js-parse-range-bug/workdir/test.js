'use strict';

const test = require('node:test');
const assert = require('node:assert');
const { parseRange } = require('./parse');

test('inclusive range', () => {
  assert.deepStrictEqual(parseRange('1-3'), [1, 2, 3]);
});

test('longer inclusive range', () => {
  assert.deepStrictEqual(parseRange('4-8'), [4, 5, 6, 7, 8]);
});

test('single value', () => {
  assert.deepStrictEqual(parseRange('5'), [5]);
});

test('single-element range', () => {
  assert.deepStrictEqual(parseRange('7-7'), [7]);
});
