# Flow — the Emdash worktree sweep (B179, 2026-10-22)

Every nightly `agent-ready-nightly` run opens a git worktree and an `emdash-<run>` branch, even on a night with no
`agent-ready` issue, and nothing removed them (10 by 2026-10-22, all empty). A daily user timer on rogueone removes the
ones that hold nothing and names the rest. It never decides that work is disposable: only an empty, settled worktree
goes.

Runbook: [software-factory.md § Worktree sweep](../runbooks/software-factory.md). Logic:
`scripts/emdash-worktree-sweep.sh` (tests: `scripts/tests/emdash-worktree-sweep.bats`, real git).

```mermaid
sequenceDiagram
    participant E as Emdash (04:00 agent-ready-nightly)
    participant W as worktree ~/emdash/worktrees/<project>/emdash-<run>
    participant T as emdash-worktree-sweep.timer (06:30 NY, user unit)
    participant S as emdash-worktree-sweep.sh --apply
    participant G as git (the weyland repo)
    E->>W: git worktree add + branch emdash-<run> (every night, issue or not)
    T->>S: start (Persistent, a missed run catches up at boot)
    S->>G: worktree list (only paths under ~/emdash/worktrees on an emdash- branch)
    alt no origin/main, or git itself fails
        S-->>T: exit 2, CANNOT CHECK (nothing removed)
    else for each candidate
        alt uncommitted or untracked change
            S-->>T: kept, named (review by hand)
        else commits not on origin/main
            S-->>T: kept, named (review by hand)
        else younger than 24 h
            S-->>T: kept (may still be running)
        else empty and settled
            S->>G: git worktree remove + git branch -D
            S-->>T: removed
        end
    end
    Note over T: the journal holds every verdict (journalctl --user -u emdash-worktree-sweep). machine-inv-drift flags the unit failing or the timer going stale.
```
