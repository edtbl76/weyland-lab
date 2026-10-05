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

**The operator recalls through its own governed path (2026-10-03):** the compositor mounts the store as a READ-ONLY
`memory` upstream — its middleware hides and refuses every memory tool except 7 read tools — so the operator gets
`memory_search_notes` etc. via the MCP gateway's `/mcp-fleet`, with its Keycloak identity, like every other read tool.
**Open WebUI recalls as the signed-in person (2026-10-04):** an MCP tool server on the gateway's `/mcp-memory`
(memory-only compositor, same 7 read tools) with `system_oauth` — the user's own Keycloak token, so the gateway sets
`X-Forwarded-User`. No shared key.

## Read-only recall — the operator and Open WebUI (2026-10-04 → 05)

Both READ through the governed MCP gateway, never Bifrost: the operator as its Keycloak client, Open WebUI as **each
signed-in person**. Every request leaves an audit line; the compositors admit no one but the gateway (and Bifrost, for
the fleet). Runbooks: [mcp-gateway.md](../runbooks/mcp-gateway.md) § Audit · [open-webui.md](../runbooks/open-webui.md).

```mermaid
sequenceDiagram
    participant P as Person (browser)
    participant OW as Open WebUI (Lab Recall)
    participant KC as Keycloak
    participant OP as weyland-operator
    participant GW as MCP gateway
    participant L as Loki
    participant CM as memory-only compositor
    participant CF as fleet compositor
    participant BM as Basic Memory :8765 (rogueone)
    participant X as any other pod

    P->>OW: ask Lab Recall what caused the GPU freeze
    OW->>KC: refresh the person's token (session lives 10h, same as the Open WebUI login)
    KC-->>OW: access token (azp open-webui, preferred_username emangini)
    OW->>GW: POST /mcp-memory, Bearer = the person's token (system_oauth)
    GW->>GW: validate JWT (JWKS) and set X-Forwarded-Consumer + X-Forwarded-User
    GW->>L: mcp-gateway-audit path=/mcp-memory actor=open-webui user=emangini status=200
    GW->>CM: tools/call search_notes
    CM->>CM: allowlist (7 read tools), search made semantic, invented filters dropped
    CM->>BM: search_notes (semantic)
    BM-->>OW: rogueone-gpu-freeze-vram (via CM and GW)
    OW-->>P: a kernel bug, conclusive 2026-08-13
    alt the Keycloak session has lapsed
        OW->>GW: POST /mcp-memory with NO token
        GW->>L: mcp-gateway-audit actor=- user=- status=401
        GW-->>OW: 401
        OW-->>P: shared memory could not be reached (never an invented note)
    end
    OP->>GW: /mcp-fleet memory_search_notes (client_credentials, azp weyland-operator)
    GW->>L: mcp-gateway-audit path=/mcp-fleet actor=weyland-operator user=- status=200
    GW->>CF: tools/call memory_search_notes
    CF->>BM: search_notes (semantic)
    X->>CM: direct POST /mcp
    CM--xX: refused by NetworkPolicy (no side door around the audit)
```

