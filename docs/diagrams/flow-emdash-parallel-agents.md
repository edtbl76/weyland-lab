# Flow: Emdash — parallel agents, one worktree per task (B104)

Emdash (`generalaction/emdash`, MIT) is a desktop supervisor over the coding-agent CLIs the lab already
has. Its one real idea — the thing a single `claude` terminal does NOT give you — is **fan-out with
isolation**: each task gets its **own git worktree + branch + agent**, several run **at once**, and you
review/compare/merge them all from **one board**. One task looks like "Claude Code in a worktree"; the
value is at N tasks in parallel.

```mermaid
flowchart TB
    Op([operator])
    Intake[Linear / GitHub / Jira issues]
    Board["Emdash board (one desktop UI)"]

    Op -->|add project: local git repo or SSH remote| Board
    Intake -.->|send a ticket into a task| Board
    Op -->|create task A| WA
    Op -->|create task B| WB
    Op -->|create task C| WC

    subgraph Parallel["parallel — each task fully isolated"]
        WA["worktree A + branch"] --> AA["agent: Claude Code"]
        WB["worktree B + branch"] --> AB["agent: codex"]
        WC["worktree C + branch"] --> AC["agent: opencode"]
    end

    AA --> DA["diff A"]
    AB --> DB["diff B"]
    AC --> DC["diff C"]
    DA --> Review
    DB --> Review
    DC --> Review
    Review["review: compare diffs, open PR, or merge"] -->|merge the ones that worked| Main[(main)]
```

Why it matters (and where it doesn't):

- **Isolation** — worktree-per-task means task A's agent can't clobber task B's files; you can run three
  experiments on the same repo at once without a mess. (You *can* do this by hand with `git worktree add`
  — Emdash just makes it one click and gives you the board.)
- **Fan-out + review in one place** — start N agents, come back, compare the N diffs, keep the winners.
  This is the parallel-attempt pattern (try three approaches, pick the best) with a UI instead of a
  terminal-juggling exercise.
- **Ticket intake + remote** — pull a Linear/GitHub issue straight into a task; drive agents on a remote
  machine over SSH (fits the lab's rogueone/mother split).
- **Not a capability, a convenience** — for a **solo** lab it is nice-to-have, not a gap: one person can
  only babysit so many parallel agents, and the isolation is achievable with the CLIs directly. That is
  why the survey rated this category "optional / low for a solo lab." Adopt it when parallel work is
  actually the bottleneck.

Demo (installed + eyes-on): [../demos/parallel-agent-emdash.md](../demos/parallel-agent-emdash.md).
Recipe + install: [../runbooks/parallel-agent-supervisor.md](../runbooks/parallel-agent-supervisor.md).

## The conveyor — `agent-ready-nightly` (B179, adopted 2026-10-12)

The unattended path the B179 trials proved: a person releases a READY issue with a label, and the 04:00 automation
picks it up with nobody steering. It runs inside the Emdash app (no app, no run; a missed slot starts on the next launch)
and stops at a local worktree: push is off, so nothing reaches GitHub until a person reviews it. Definition of record:
[runbooks/software-factory.md](../runbooks/software-factory.md) § The conveyor.

```mermaid
sequenceDiagram
    participant P as person
    participant L as Linear (Weyland Lab)
    participant E as Emdash scheduler (rogueone)
    participant C as Claude Code (worktree, auto-approve)
    participant R as issue-readiness.sh
    P->>R: check EMA-### (must print READY)
    P->>L: add label agent-ready
    Note over E: 04:00 NY, or on launch if the slot was missed (24 h deadline)
    E->>C: new worktree + branch from origin/main (push OFF), the conveyor prompt
    C->>L: oldest open issue labelled agent-ready?
    alt none
        L-->>C: empty (label + project verified)
        C-->>E: "none found", stop
    else an issue
        L-->>C: EMA-###
        C->>R: EMA-### --no-comment
        alt not READY
            R-->>C: what is missing
            C-->>E: stop, say why
        else READY
            C->>C: implement, run the issue's tests, report each criterion
            C-->>E: changes left uncommitted in the worktree
        end
    end
    P->>C: morning: read the transcript + worktree
    P->>L: if adopted: bring into main, remove agent-ready
```
