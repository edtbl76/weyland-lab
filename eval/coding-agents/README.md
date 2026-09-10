# Coding-agent evaluation harness (B104)

The lab scores its **RAG** (B84/B96 golden set) but has had nothing that scores its **coding agents**.
This is that: a small suite of self-contained coding tasks, a runner that hands each task to an agent in
an isolated workspace, and a **fail-closed** grader that only calls a run a pass when the task's own tests
pass. Results append to a committed baseline (`tests/eval/coding-agents.tsv`), the way the perf baseline
records throughput — so agents can be compared over time.

## Layout

```
eval/coding-agents/
  agents.json            # agent name -> headless invocation (claude/opencode/codex + mock-*)
  tasks/<id>/
    task.md              # the prompt handed to the agent
    workdir/             # seed files: buggy code + a FAILING stdlib test
    grade.sh             # runs the test; prints `GRADE: PASS`/`GRADE: FAIL` as its verdict line
    solution/            # the known-good fix (used only by the mock-pass agent)
    meta.json            # {id, language, timeout_s}
scripts/coding-agent-eval.sh      # the runner
tests/eval/coding-agents.tsv      # append-only baseline (agent·task·pass·result·duration·rc·ts)
scripts/tests/coding-agent-eval.bats   # decision-logic tests (fail-closed properties)
docs/runbooks/coding-agent-eval.md     # how the operator runs a real sweep
```

## How it scores (fail-closed by design)

For each `(agent, task)` the runner:
1. copies `workdir/` into a throwaway **git** rundir (a real repo, so agents that need one are happy);
2. **Red pre-check** — runs the grader BEFORE the agent; the fixture MUST fail. A fixture that already
   passes is `RED-BROKEN`, never a free pass;
3. runs the agent (stdin `/dev/null`, bounded by `timeout_s`);
4. **grades** — the task passes ONLY if the grader prints `GRADE: PASS`. No verdict line → `ERROR`; a
   timeout → `TIMEOUT`; both score `pass=0`.

This mirrors the lab's hard-won rule that an absent or ambiguous result must never stand for success (see
the `code-generation` / `deployment-execution` corrections in project memory).

## Run it

```
scripts/coding-agent-eval.sh --list                       # agents + tasks
scripts/coding-agent-eval.sh --agent mock-pass --all      # $0 self-test of the harness (expect all PASS)
scripts/coding-agent-eval.sh --agent codex --all          # a real agent over every task  (operator, on-demand)
scripts/coding-agent-eval.sh --all-agents --all           # full sweep
```

Real-agent runs spend real quota/time — **on-demand only, never CI, never scheduled.** See the runbook
for the codex sandbox caveat on this host.

## Adding a task

Drop a new `tasks/<id>/` with `task.md`, `workdir/` (buggy code + a **failing** stdlib test), a `grade.sh`
that emits `GRADE: PASS`/`GRADE: FAIL` as its last line, a `solution/`, and `meta.json`. Keep graders on
the language runtimes already present (python3, node stdlib) so a task needs no install and stays $0 and
deterministic. The bats suite exercises the runner, not your task — but the Red pre-check will reject a
fixture whose test doesn't actually fail first.
