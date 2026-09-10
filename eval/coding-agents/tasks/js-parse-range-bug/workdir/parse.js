'use strict';

// parseRange("1-3") -> [1, 2, 3]. A bare number "5" -> [5].
//
// BUG: the range branch is end-exclusive — it produces [1, 2] for "1-3"
// instead of [1, 2, 3]. The upper bound must be inclusive.
function parseRange(spec) {
  const parts = String(spec).split('-');
  if (parts.length === 1) {
    return [Number(parts[0])];
  }
  const lo = Number(parts[0]);
  const hi = Number(parts[1]);
  const out = [];
  for (let i = lo; i < hi; i++) {
    out.push(i);
  }
  return out;
}

module.exports = { parseRange };
