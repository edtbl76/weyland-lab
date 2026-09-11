# Flow: Plannotator — plan + diff review round-trip (B167)

Plannotator (`backnotprop/plannotator`, MIT/Apache-2.0) is a **local** human review surface for coding agents.
Two entry points — the agent-initiated **plan review** (hooks `ExitPlanMode`) and the human-initiated **diff
review** (`/plannotator-review`) — both open a browser UI served by a local process, take annotations, and feed
them back to the agent. Workstation tool (beside the agent on rogueone), no cluster footprint. Eval:
[../concepts/plannotator-eval.md](../concepts/plannotator-eval.md); ops: [../runbooks/plannotator.md](../runbooks/plannotator.md).

```mermaid
flowchart TB
    Agent([coding agent: Claude Code])
    Human([operator])

    subgraph Triggers["two entry points"]
        Plan["agent calls ExitPlanMode<br/>(PermissionRequest hook)"]
        Diff["operator runs /plannotator-review<br/>(user-invocation-only)"]
    end

    Server["Plannotator local server<br/>(~/.local/bin, local port)"]
    UI["browser review UI<br/>plan markdown OR side-by-side diff"]

    Agent -->|finishes planning| Plan
    Human -->|uncommitted diff / PR / MR| Diff
    Plan --> Server
    Diff --> Server
    Server --> UI
    Human -->|annotate lines / redlines| UI

    UI -->|Approve / LGTM| Approve["agent proceeds"]
    UI -->|Deny / send feedback| Feedback["structured annotations<br/>→ back to agent session"]
    Approve --> Agent
    Feedback --> Revise["agent revises against the notes"]
    Revise --> Agent
```

- **Plan review** is the flagship: it intercepts Claude Code's native `ExitPlanMode` gate, so the plan-approval
  step becomes an annotatable page instead of a wall of terminal text. **Deny** returns the annotations as
  structured feedback and the agent revises.
- **Diff review** covers written code (uncommitted changes or a PR/MR) with line-level annotation and a one-click
  round-trip back to the session.
- **Local by default** — set `PLANNOTATOR_AI=disabled` + `PLANNOTATOR_SHARE=disabled` to keep every byte on the
  LAN (only Ask-AI and link-sharing would egress otherwise).
