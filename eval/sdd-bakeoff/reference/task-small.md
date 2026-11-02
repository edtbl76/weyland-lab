# Task: alert-rule tests can silently run a different scenario than the one written

**Repo:** this repository (a homelab platform). **Area:** `scripts/tests/alert-rules.bats` and its fixtures in
`scripts/tests/fixtures/alert-rules/`.

**Problem.** `alert-rules.bats` extracts the real alert rules from the PrometheusRule manifests and runs promtool unit
tests (`promtool test rules`) against the fixtures. The harness re-reads each fixture with PyYAML before promtool sees
it. PyYAML follows YAML 1.1, so an unquoted series value such as `values: 0x15` is parsed as the HEX integer 21, not as
promtool's "0 repeated 15 times". The test then runs a different scenario from the one written, and can pass for the
wrong reason, with nothing reporting it.

**Required behaviour.**
1. The harness must FAIL a test case whose fixture has any `input_series` `values` that did not parse as a string, with a
   message that names the offending value and tells the author to quote it. It must never silently run such a fixture.
2. Every existing alert-rules test must still pass afterwards, which means fixing any existing fixture that has the
   problem, without changing what that test is meant to check.

**Acceptance criteria.**
- [ ] A fixture with an unquoted hex-looking series value (e.g. `values: 0x15`) makes its alert-rules test fail.
- [ ] Every existing test in `scripts/tests/alert-rules.bats` passes.
- [ ] Nothing outside `scripts/tests/` changes.

**Tools available on PATH:** `bats`, `promtool`, `python3` (with PyYAML). Run the suite with
`bats scripts/tests/alert-rules.bats`.
