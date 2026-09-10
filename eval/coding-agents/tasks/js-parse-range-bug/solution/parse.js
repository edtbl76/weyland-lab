'use strict';

// parseRange("1-3") -> [1, 2, 3]. A bare number "5" -> [5].
function parseRange(spec) {
  const parts = String(spec).split('-');
  if (parts.length === 1) {
    return [Number(parts[0])];
  }
  const lo = Number(parts[0]);
  const hi = Number(parts[1]);
  const out = [];
  for (let i = lo; i <= hi; i++) {
    out.push(i);
  }
  return out;
}

module.exports = { parseRange };
