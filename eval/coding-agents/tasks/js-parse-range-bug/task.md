# Task: make `parseRange()` upper bound inclusive

`parse.js` exports `parseRange(spec)`. `parseRange("1-3")` should return
`[1, 2, 3]`, but it currently returns `[1, 2]` — the range is end-exclusive.

Fix `parseRange()` in `parse.js` so the upper bound is inclusive and all tests
in `test.js` pass. Do not change the tests.

Verify with:

    node --test
