# Flow: Prompt federation — one SoT for prompts + measurement (B103)

Bifrost is the single source of truth; `sync_prompts.py` mirrors every prompt OUT to Langfuse + MLflow (bidirectional,
idempotent), and apps fetch from Langfuse at runtime — so each LLM trace is tagged with the exact prompt version.

```mermaid
sequenceDiagram
    autonumber
    participant Au as Author
    participant BF as Bifrost (SoT)
    participant SY as sync_prompts.py<br/>(Dagster registrations asset)
    participant LF as Langfuse Prompts
    participant ML as MLflow Registry
    participant AP as App<br/>(tool-server · operator · agent)
    Au->>BF: author / edit a prompt
    SY->>BF: read prompts
    SY->>LF: push (normalized, chat + {{var}})
    SY->>ML: push (mirror, string + {var})
    LF-->>SY: native playground edits reconciled back to BF
    AP->>LF: get_prompt at runtime
    LF-->>AP: prompt vN
    AP->>AP: LLM call, trace tagged "Prompt name vN"
    Note over AP,LF: linkage is created at fetch time, so the SoT (Bifrost) is decoupled from where the linkage lives (Langfuse)
```

Demo: [demos/prompt-federation.md](../demos/prompt-federation.md).
