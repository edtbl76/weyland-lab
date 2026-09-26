# Flow: Multi-Harness — Linear issue → any harness → shared platform (B181 live, B182 shared memory planned)

One Linear issue can be worked by **more than one harness** against the same platform. The live path today (verified
2026-09-25): Linear's "Work on issue" launcher hands the issue to **Codex** (`codex://` → ChatGPT desktop), and Codex
reads the full issue through **Linear's hosted MCP** and the lab's tools through **Bifrost**; **Claude Code** reaches
the same two MCP servers. The **shared agent memory** step is **planned (B182)** — store, transport and gateway are all
TBD, so it is drawn as an optional block, not a live call. See [concepts/multi-harness.md](../concepts/multi-harness.md),
[design/shared-agent-memory-design.md](../design/shared-agent-memory-design.md).

```mermaid
sequenceDiagram
    participant U as Edward (Linear in Chrome, rogueone)
    participant L as Linear (app + hosted MCP)
    participant H as Harness (Codex or Claude Code)
    participant B as Bifrost (MCP agent edge)
    participant M as Shared agent memory (TBD, B182)
    participant P as Model provider (ChatGPT sub or Anthropic)
    U->>L: Work on issue (W then O)
    L->>H: launcher link (codex:// today, claude-cli:// planned)
    H->>L: get_issue (Linear MCP, OAuth)
    L-->>H: title, description, status
    opt planned (B182) - not built
        H->>M: recall lessons + decisions for this area
        M-->>H: matching notes
    end
    H->>B: tools/list + tool calls (x-bf-vk)
    B-->>H: fleet results (Grafana, Trino, DataHub, ...)
    H->>P: reasoning + tool loop
    P-->>H: plan and edits
    opt planned (B182) - not built
        H->>M: write new lesson or decision
    end
    H->>L: update issue status or comment (Linear MCP)
    H-->>U: result in the terminal / desktop app
```

**Why this shape.** Every shared concern sits behind a protocol every harness already speaks (MCP), so adding a
harness is one config entry, not an integration: Linear and Bifrost are live, memory is the missing third. Keeping
memory per-harness (the status quo) means a lesson learned in Claude Code is invisible to Codex — the drift B182 exists
to remove. Runbook: [runbooks/coding-agents.md](../runbooks/coding-agents.md) (Codex + Linear, the bubblewrap fix).
