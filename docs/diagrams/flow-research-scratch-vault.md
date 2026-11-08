# Flow — research scratch vault (B187)

A throwaway claude-obsidian vault for one research task, on rogueone. Sources go in, Claude writes cited notes, and
questions are answered from those notes. Nothing is written until the owner approves the exact plan. The vault is
deleted when the task ends. Operate: [runbooks/research-scratch-vault.md](../runbooks/research-scratch-vault.md).

```mermaid
sequenceDiagram
    participant O as Owner
    participant C as Claude Code session (--plugin-dir claude-obsidian)
    participant P as claude-obsidian core (Python CLI)
    participant V as Scratch vault (inbox, wiki, ledgers)
    O->>V: put text sources in inbox/ (each starts with its Source URL)
    O->>C: /claude-obsidian:wiki-ingest
    C->>V: read every inbox file in full
    C->>P: draft pages, source ledger, claim ledger (accepted, provisional, contested)
    P-->>C: plan with approved_plan_sha256 (nothing written yet)
    C-->>O: files to create and update, claims, partial sources
    alt owner says no
        O-->>C: no
        Note over C,V: drafts stay in the session scratchpad, the vault is unchanged
    else owner says yes
        O->>C: yes
        C->>P: workflow apply with the same hash
        alt a target changed since it was read
            P-->>C: conflict, nothing applied
        else unchanged
            P->>V: one transaction (backups journaled, rolled back if the apply fails)
            P-->>C: operation id and exact changed paths
            C->>P: lint (dead links, orphans, metadata)
        end
    end
    O->>C: /claude-obsidian:wiki-query question
    C->>V: read the relevant pages and claims
    C-->>O: answer citing pages and claim ids, gaps stated, vault unchanged
    Note over O,V: after /compact the session re-reads the vault, so the answer keeps its facts and citations
    O->>V: task done, rm -r the folder
```

- **Approval binds to the plan.** The hash covers the exact operation; a changed plan needs a new approval.
- **Disagreement stays visible.** A claim with a supporting and a contradicting source is recorded as `contested`, and
  query answers report both sides.
- **Scratch only.** Never pointed at the shared agent memory or the owner's own vault.
