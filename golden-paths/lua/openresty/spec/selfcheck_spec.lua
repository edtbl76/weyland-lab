-- Deliberately-failing spec, tagged `#selfcheck` — proves the lua lane PROPAGATES failure.
-- A normal `busted` run excludes it (`.busted` default sets exclude-tags = "selfcheck"), so it passes.
-- The lane self-check runs `busted --run=selfcheck` (or `busted --tags=selfcheck`), which selects ONLY
-- this case and must exit non-zero. Tag-selected (not a name filter) → fail-closed: if the tag is
-- removed, `busted --tags=selfcheck` matches zero cases and busted exits non-zero on "no tests" too,
-- so the guard still reports the lane as broken rather than silently passing.
describe("selfcheck #selfcheck", function()
  it("deliberate failure", function()
    assert.are.equal(
      "expected",
      "actual",
      "selfcheck: the golden-path lua lane must surface this failure (exit non-zero)"
    )
  end)
end)
