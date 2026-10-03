# Flow: shared agent memory — one store, two views (B182)

The store **is the directory of Markdown notes** on rogueone (`~/agent-memory/weyland`). Claude Code reads and writes
the files natively (its memory dir is a symlink to that directory). **Basic Memory** indexes the same files and serves
them over MCP, so Codex and the other agents reach them through Bifrost. No copy, no sync: a note written either way is
visible the other way in under a second (measured 2026-10-03). See
[runbooks/shared-agent-memory.md](../runbooks/shared-agent-memory.md) ·
[design/shared-agent-memory-design.md](../design/shared-agent-memory-design.md) · arch.md §8d.

```mermaid
sequenceDiagram
    participant CC as Claude Code (rogueone)
    participant N as notes ~/agent-memory/weyland
    participant BM as Basic Memory :8765 (rogueone)
    participant FW as ufw (rogueone)
    participant BF as Bifrost /mcp (mother)
    participant CX as Codex (rogueone)
    participant W as agent-memory-watch (every 15 min)
    participant K as Kuma push monitor

    Note over CC,N: native view — the memory dir is a symlink to the notes
    CC->>N: write a lesson as a plain .md file + a pointer in MEMORY.md
    BM->>N: watch the directory and index the change (< 1 s)
    Note over CX,BF: shared view — the Agent_Memory tools, coding-agents key
    CX->>BF: Agent_Memory-search_notes("…") with header x-bf-vk
    BF->>FW: TCP to 192.168.1.230:8765 from mother (192.168.1.243)
    FW->>BM: allowed (only mother is admitted to 8765)
    BM-->>BF: matching notes
    BF-->>CX: results, including the note Claude Code just wrote
    CX->>BF: Agent_Memory-write_note(title, directory, content)
    BF->>BM: write_note
    BM->>N: the note lands as a .md file
    CC->>N: reads it as an ordinary file next session (or now)
    alt the store does not answer
        BF-->>CX: MCP error — reported as UNREACHABLE, never as "no memory"
    end
    loop every 15 min
        W->>N: gitleaks 8.21.2 scan, findings redacted
        W->>BM: check-shared-memory --read-only (reachable, index count == file count)
        W->>K: push up, or down with the reason (secret found / store unreachable / scanner failed)
    end
```

**What is not wired yet:** the weyland-operator gets its tools from the governed MCP gateway (`/mcp-fleet`), not
Bifrost, so its read-only `Agent_Memory` access on the operator key has no consumer yet. Open WebUI's key is
undecided. Both are planned edges in the C4 `harnesses` view.
