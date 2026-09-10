# Demo: coding-agent eval harness + perf ratchet (B104)

Repo-tooling demo — the **CLI walkthrough is the whole demo** (no UI), it is **RUN against real fixtures**,
and it includes the **negative cases with their exit codes** (a guard nobody has watched fail is not a
guard). Both tools are `$0`; the eval self-test uses mock agents, so it spends no API quota.

## Coding-agent eval harness

Design + fail-closed grading flow: [../diagrams/flow-coding-agent-eval.md](../diagrams/flow-coding-agent-eval.md).
Runbook: [../runbooks/coding-agent-eval.md](../runbooks/coding-agent-eval.md).

```
$ bash scripts/coding-agent-eval.sh --list
agents:
  - claude / opencode / codex / mock-pass / mock-noop
tasks:
  - js-parse-range-bug / py-median-bug

# POSITIVE — the mock that applies the known fix passes both tasks:
$ bash scripts/coding-agent-eval.sh --agent mock-pass --all
  mock-pass  js-parse-range-bug  PASS
  mock-pass  py-median-bug       PASS
  2/2 passed

# NEGATIVE — the mock that does nothing fails both (fail-closed, pass=0):
$ bash scripts/coding-agent-eval.sh --agent mock-noop --all
  mock-noop  js-parse-range-bug  FAIL
  mock-noop  py-median-bug       FAIL
  0/2 passed
```

The fail-closed branches (RED-BROKEN / TIMEOUT / ERROR never scoring a pass) are proven live by
`scripts/tests/coding-agent-eval.bats` (14 cases). Real-agent runs (`--agent codex`, etc.) are
operator-on-demand — see the runbook's sandbox caveat.

## Perf regression ratchet

Runbook: [../runbooks/perf-baseline.md](../runbooks/perf-baseline.md).

```
# ADVISORY (default) — reports drift vs each target's floor, exit 0:
$ bash scripts/perf-ratchet.sh
target         latest    floor   delta%    err%  verdict
trino            27.4     71.6    -61.7    0.00  ok
gateway           6.0        -        -    0.00  no-prior (advisory)
toolserver       45.0        -        -    0.00  no-prior (advisory)
no regressions.                                   # exit 0

# NEGATIVE — a synthetic regression under enforce mode exits non-zero:
#   (floor p95=20ms, latest=30ms > 20*1.25)
$ PERF_RATCHET_ENFORCE=1 bash scripts/perf-ratchet.sh   # against a regressed baseline
  svc  30.0  20.0  +50.0  0.00  REGRESSION p95
  REGRESSIONS 1
  → exit 1
```

Fail-closed behaviour (missing / malformed baseline → exit 2, never a silent "no regression") is locked by
`scripts/tests/perf-ratchet.bats` (11 cases).

## Cleanup

Read-only against the repo + the committed baselines. The eval harness works in throwaway `mktemp` git
rundirs that it removes after each run; `tests/eval/coding-agents.tsv` is header-only until an operator
records a real run. Nothing to tear down.
