# Flow: several coding agents side by side in Herdr (B257)

Herdr's background server owns each agent's terminal, so the agents outlive the client (a closed terminal or a dropped
SSH connection). It reads each agent's state from its screen (or the agent's own reports) and serves a local socket
that the CLI, scripts and other agents use. Runbook: [herdr.md](../runbooks/herdr.md);
decision: [ADR-0018](../adr/0018-adopt-herdr-for-interactive-multi-agent-work.md).

```mermaid
sequenceDiagram
    participant O as Owner (TUI client or CLI)
    participant S as Herdr server (rogueone, local socket)
    participant A as Agent A pane (e.g. Claude Code)
    participant B as Agent B pane (e.g. Codex)
    participant H as herdr.dev
    O->>S: herdr (attach) / agent start
    S->>A: spawn in its own pty
    S->>B: spawn in its own pty
    S->>H: GET latest.json (version check only, start-up + every 30 min)
    O->>S: agent prompt A, agent prompt B
    loop every screen update
        S->>A: read the live bottom of the screen
        S->>B: read the live bottom of the screen
        S-->>O: working / blocked / idle per pane
    end
    A->>S: herdr agent prompt B "task" --wait (needs permission to run herdr)
    S->>B: type the prompt
    B-->>S: back to idle (finished)
    S-->>A: wait returns, then A reads the pane of B
    Note over O,S: client closed or SSH dropped: A and B keep running, a server or machine restart ends them
```
