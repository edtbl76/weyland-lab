# Flow: Operator agent (`weyland-operator`, B66)

Text the lab from anywhere → it acts. A LangGraph ReAct agent — **local `qwen2.5:7b` primary with Haiku failover**
(see [flow-operator-brain.md](flow-operator-brain.md)) — over the tool-server's read + act tools **plus the read-only MCP fleet** (`/mcp-fleet`) **and a `delegate_to_realm`
hand-off to the Realm of Agents** (B17 A2A), fronted by **Telegram long-poll**, with **per-chat Postgres session
memory** and an **app-level confirm-step** on every state-changing action (the operator lane Hermes vacated). Read
tools and Realm delegation are called freely; act tools are **PROPOSE-only** — the LLM proposes, the user confirms,
the *app* fires. See [demos/operator.md](../demos/operator.md), [runbooks/operator.md](../runbooks/operator.md),
[runbooks/mcp-fleet.md](../runbooks/mcp-fleet.md), [demos/realm-of-agents.md](../demos/realm-of-agents.md),
[flow-operator-brain.md](flow-operator-brain.md), [flow-incident-sweep.md](flow-incident-sweep.md).

```mermaid
sequenceDiagram
    participant U as You (Telegram)
    participant O as weyland-operator (LangGraph)
    participant S as Postgres (session)
    participant G as weyland-guard
    participant L as brain (local qwen2.5:7b · Haiku failover)
    participant T as tool-server (/mcp + /mcp-act)
    participant F as MCP fleet /mcp-fleet (grafana·trino·k8s·postgres·neo4j·datahub)
    participant R as Realm of Agents (Gná → 24 specialists)
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
        alt read tool — tool-server
            O->>T: /status · /context/ask (called freely)
            T-->>O: result
        else read tool — MCP fleet
            O->>F: grafana_* · trino_* · k8s_* · … (read-only)
            F-->>O: result
        else delegate_to_realm
            O->>R: POST /route {message} (A2A hand-off — Gná dispatches)
            R-->>O: {routed_to, role, realm, answer}
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
