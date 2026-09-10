# Runbook — coding-agent evaluation (B104)

Scores the lab's coding agents (Claude Code · opencode · codex) on a suite of self-contained bug-fix
tasks and records the result to a committed baseline. This is the coding-agent counterpart to the RAG
golden set (B84/B96) and the perf baseline ([[perf-baseline]]). **On-demand only** — a real-agent sweep
spends API quota and minutes; it is never wired into CI or a schedule.

Design + layout: `eval/coding-agents/README.md`. Fail-closed grading rationale lives there and in the
`code-generation` corrections in project memory.

## Self-test the harness (free)

```
bash scripts/coding-agent-eval.sh --list
bash scripts/coding-agent-eval.sh --agent mock-pass --all    # expect: all PASS
bash scripts/coding-agent-eval.sh --agent mock-noop --all    # expect: all FAIL
```

`mock-pass` applies the known fix; `mock-noop` does nothing. Together they prove the Red pre-check,
fail-closed grading, and TSV recording without spending any agent quota.

## Run a real sweep (operator, on-demand)

```
bash scripts/coding-agent-eval.sh --agent codex --all        # one agent, every task
bash scripts/coding-agent-eval.sh --all-agents --all         # every agent, every task
```

Each run appends rows to `tests/eval/coding-agents.tsv`:

```
agent  task  pass  result  duration_s  agent_rc  timestamp
```

`result` is one of `PASS` · `FAIL` · `ERROR` (grader printed no verdict) · `TIMEOUT` · `RED-BROKEN`
(fixture wasn't failing before the agent ran). `pass` is `1` only for a clean `PASS`.

## Host caveat — codex sandbox (rogueone/mother)

codex's built-in sandbox uses **bubblewrap**, which needs user namespaces. They are disabled on
rogueone/mother, so a `--sandbox workspace-write` codex can reason the fix but **cannot write it** (it
reports "the sandbox helper itself is failing"). The runner already isolates every run in a disposable
git rundir, so the codex entry in `agents.json` uses `--dangerously-bypass-approvals-and-sandbox` — the
flag codex documents as *"intended solely for environments that are externally sandboxed"*, which the
rundir is. Run codex evals from an **operator terminal**: a background Claude Code session's safety
classifier blocks that flag by design, so the automated session cannot capture codex rows itself.
(claude and opencode run headless without user namespaces and need no such flag.)

If you would rather keep codex's own sandbox, enable unprivileged user namespaces on the host
(`sysctl kernel.unprivileged_userns_clone=1`, distro-dependent) — an infra change, out of this harness's
scope, and not required given the rundir isolation.

## Interpreting a sweep

- A row is a single (agent, task) attempt; compare `pass`/`result` and `duration_s` across agents.
- Two tasks ship today (`py-median-bug`, `js-parse-range-bug`) — a deliberately small, deterministic
  seed. Grow the suite by adding `tasks/<id>/` (see the README); breadth is what makes the comparison
  meaningful, so add tasks before drawing conclusions from a two-task sample.
- The baseline is append-only; keep it in git so agent-vs-agent and version-over-version trends survive.

## Guardrails covering this

`scripts/tests/coding-agent-eval.bats` (run in the `shell-tests` CI lane) locks the fail-closed
properties: PASS only on a real `GRADE: PASS`, no-verdict → ERROR, already-passing fixture → RED-BROKEN,
overrun → TIMEOUT, unknown/blank agent → loud error. It uses bash-only synthetic fixtures, so it needs
only python3 (already added to the lane) — no per-language toolchain.
