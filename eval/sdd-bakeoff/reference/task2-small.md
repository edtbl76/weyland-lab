# Change request: the alert-test harness must also refuse empty series values

**Repo:** this repository. **Area:** `scripts/tests/alert-rules.bats` and `scripts/tests/fixtures/alert-rules/`.

**Background.** The harness already refuses a fixture whose `input_series` `values` did not parse as a string (a bare
`0x15` is hex 21 to PyYAML). It does not catch a `values` that is a string but empty or only whitespace
(`values: ""`). promtool then runs a series with no samples, an alert can stay silent for the wrong reason, and the
test passes.

**Required behaviour.**
1. A fixture whose `input_series` entry has `values` missing, `null`, an empty string, or whitespace only must make
   its alert-rules test FAIL, with a message that names the series.
2. Everything the harness refused before is still refused, and every existing alert-rules test still passes.

**Acceptance criteria.**
- [ ] A fixture with `values: ""` (or only spaces) makes its test fail, naming the series.
- [ ] Every existing test in `scripts/tests/alert-rules.bats` passes; non-string values are still refused.
- [ ] Nothing outside `scripts/tests/` changes.

**Tools available on PATH:** `bats`, `promtool`, `python3` (with PyYAML).
