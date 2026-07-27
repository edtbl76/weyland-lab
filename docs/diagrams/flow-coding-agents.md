# Flow: Coding Agents (B15 — `$0` agentic coding, direct-to-provider)

A terminal coding agent (opencode / Cline / Pi / Codex) drives a multi-step task — write a function + a pytest, run it —
by looping tool-calls against a **hosted model reached DIRECTLY**, not through the MLflow AI Gateway. Two independent
findings force the direct path: the gateway crashes on a hosted multi-turn tool loop (turn-2 `json.loads("")` inside
MLflow) and its response-stage guardrails block streaming; and rogueone's 16GB local models can't drive tools reliably.
Keys come from the gitignored `scripts/.env` (or the ChatGPT sub via "Sign in with ChatGPT" for Cline/Codex). See
[runbooks/coding-agents.md](../runbooks/coding-agents.md).

```mermaid
sequenceDiagram
    participant D as Dev (rogueone)
    participant A as Coding agent (opencode/Cline/Pi/Codex)
    participant P as Provider (DIRECT — Mistral/OpenRouter/Gemini, or ChatGPT sub GPT-5.5)
    participant FS as Project files + shell
    D->>A: "write reverse.py + test_reverse.py, run pytest"
    A->>P: chat/completions (messages + tools, stream) — key from .env / ChatGPT sub
    Note over A,P: DIRECT to provider, NOT the gateway (gateway 500s on multi-turn hosted tool loops)
    P-->>A: tool_call write(reverse.py)
    A->>FS: write reverse.py (relative path per AGENTS.md)
    A->>P: tool result + continue
    P-->>A: tool_call write(test_reverse.py)
    A->>FS: write test_reverse.py
    A->>P: tool result + continue
    P-->>A: tool_call bash(pytest)
    A->>FS: run pytest
    FS-->>A: N passed
    P-->>A: final message
    A-->>D: done — both files written, tests green ($0)
```

**Why not the alternatives** (all ruled out — see runbook): the **MLflow AI Gateway** dies on the second tool turn
for hosted providers and buffers-blocks streaming; **local 16GB models** leak tool-calls as text / hallucinate tool
names / can't disable thinking; a **ChatGPT sub is not an API** (use "Sign in with ChatGPT" in Cline/Codex — the raw
`sk-` key is dead), and a **Claude Pro/Max sub via a third-party agent** is the B26 ToS gray area (sanctioned
Claude-coding = Claude Code, B29 — see [flow-agent-mcp.md](flow-agent-mcp.md)). Related:
[flow-mlflow-gateway.md](flow-mlflow-gateway.md) (the gateway that these deliberately bypass).
