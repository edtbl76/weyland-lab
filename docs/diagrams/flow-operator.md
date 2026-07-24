# Flow: Operator agent (`weyland-operator`, B66)

Text the lab from anywhere → it acts. A LangGraph ReAct agent (`gpt-oss:20b`) over the tool-server's read + act tools,
fronted by **Telegram long-poll**, with **per-chat Postgres session memory** and an **app-level confirm-step** on every
state-changing action (the operator lane Hermes vacated). Read tools are called freely; act tools are **PROPOSE-only** —
the LLM proposes, the user confirms, the *app* fires. See [demos/operator.md](../demos/operator.md) +
[runbooks/operator.md](../runbooks/operator.md).

```mermaid
sequenceDiagram
    participant U as You (Telegram)
    participant O as weyland-operator (LangGraph)
    participant S as Postgres (session)
    participant G as weyland-guard
    participant L as Ollama (gpt-oss:20b)
    participant T as tool-server (/mcp + /mcp-act)
    U->>O: message (long-poll getUpdates)
    Note over O: allowlist check
    O->>S: load(chat_id) → history, pending_action
    alt pending_action AND message is "yes"
        O->>T: act.fire — /pipeline/trigger · /evals/* (APP fires, not the LLM)
        T-->>O: run_id
        O->>S: save(history, pending=None)
        O-->>U: ✅ Launched <job> — run <id>
    else pending_action AND message is "no"
        O->>S: save(pending=None)
        O-->>U: Cancelled
    else normal message
        O->>G: /guard/input (fail-open)
        O->>L: ReAct loop (system + history + message)
        alt read tool
            O->>T: /status · /context/ask (called freely)
            T-->>O: result
        else propose_act
            L-->>O: proposal {tool, job_name, summary}
        end
        O->>G: /guard/output (reply or proposal)
        alt proposal returned
            O->>S: save(history, pending=proposal)
            O-->>U: ⚠️ Confirm …? yes/no
        else grounded reply
            O->>S: save(history, pending=None)
            O-->>U: reply
        end
    end
    Note over O: every message → one MLflow Trace (operator experiment)
```
