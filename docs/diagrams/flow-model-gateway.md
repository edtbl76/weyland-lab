# Flow: Model-Gateway Routing (B26 → B111, LiteLLM use-case router)

Hosted-model calls go through **LiteLLM on mother**, never direct from clients. LiteLLM is the platform's
**use-case router**: a client sends only a `wl-*` alias (`wl-default`/`speed`/`coding`/`agentic`/`rag`/`reason`/
`judge`/`search`/`big-oss`) and LiteLLM resolves it to a **primary + a server-side fallback chain**, failing over
on network / 5xx / 429 / timeout down to a free, always-on rung. **Hosted lanes egress THROUGH Bifrost**
(2026-08-01): `LiteLLM → Bifrost → provider` (Anthropic `claude-haiku-4-5` / Groq `gpt-oss-120b` / opencode-zen
`kimi-k3` / Gemini / xAI); Bifrost records provider cost/tokens/latency + per-VK attribution (`realm-llm` VK). The
**local Ollama lanes** (`wl-rag`/`wl-reason`/`wl-judge`) stay **DIRECT** to rogueone and never leave the box. See
[llm-routing.md](../llm-routing.md), [runbooks/model-gateway.md](../runbooks/model-gateway.md).

```mermaid
sequenceDiagram
    participant Cl as Client (operator / Realm / Open WebUI / curl)
    participant LL as LiteLLM /v1 (mother:30400, litellm.weyland.lab)
    participant BF as Bifrost (bifrost.weyland.lab, realm-llm VK)
    participant PR as Provider (Anthropic haiku-4.5 · Groq gpt-oss-120b · opencode-zen kimi-k3 · Gemini · xAI)
    participant OL as Ollama (rogueone 192.168.1.230:11434, local)
    participant PM as Prometheus (request + spend)
    participant Tg as Telegram (alerts)
    Cl->>LL: POST /v1/chat/completions {model = wl-*}
    LL->>LL: resolve alias -> primary + fallback chain
    alt hosted lane (wl-default/speed/coding/agentic/search/big-oss)
        LL->>BF: egress via Bifrost (primary rung)
        alt primary healthy
            BF->>PR: provider call
            PR-->>BF: completion
        else network / 5xx / 429 / timeout
            BF-->>LL: error
            LL->>BF: walk chain -> next rung (chain ends free/always-on)
            BF->>PR: provider call
            PR-->>BF: completion
        end
        BF-->>LL: completion (records cost/tokens/latency + per-VK: realm-llm)
    else local lane (wl-rag/wl-reason/wl-judge)
        LL->>OL: DIRECT to rogueone (on-box, never egresses)
        OL-->>LL: completion
    end
    LL->>PM: emit request + spend metrics
    LL-->>Cl: completion (model group = wl-*)
    Note over PM,Tg: spend / off-box-egress alert -> Alertmanager -> Telegram
```
