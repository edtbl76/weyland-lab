# Flow: Model-Gateway Routing (B26, LiteLLM)

Hosted-model calls go through **LiteLLM on mother**, never direct from clients. Free tiers only (Gemini +
OpenRouter wildcard). Off-box egress is a deliberate valve with spend alerts; Hermes' local lanes (Ollama)
never leave the box and bypass this entirely.

```mermaid
sequenceDiagram
    participant Cl as Client (Hermes planning / Open WebUI / curl)
    participant LL as LiteLLM /v1 (mother:30400, litellm.weyland.lab)
    participant GM as Gemini (free tier)
    participant OR as OpenRouter (free models)
    participant PM as Prometheus (request + spend)
    participant Tg as Telegram (alerts)
    Cl->>LL: POST /v1/chat/completions {model}
    LL->>LL: resolve model -> provider route
    alt Gemini-mapped
        LL->>GM: egress (off-box)
        GM-->>LL: completion
    else OpenRouter-mapped
        LL->>OR: egress (off-box)
        OR-->>LL: completion
    end
    LL->>PM: emit request + spend metrics
    LL-->>Cl: completion
    Note over PM,Tg: spend / off-box-egress alert -> Alertmanager -> Telegram
```
