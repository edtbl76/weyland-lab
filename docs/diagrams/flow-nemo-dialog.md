# Flow: NeMo Dialog Guard (B115 — the guarded `weyland-operator` chat model)

The **Dialog** layer of the guardrails platform. Open WebUI offers a guarded **`weyland-operator`** model (an OpenAI
connection to `nemo-guardrails`) alongside the raw Ollama models. NeMo applies the input + topical rails via
`self check input` (an LLM judge — the Colang dialog rail wouldn't fire); off-domain / jailbreak requests are refused
with the operator message, on-topic passes to the main model. See [runbooks/guardrails.md](../runbooks/guardrails.md).

```mermaid
sequenceDiagram
    participant U as User (chat.weyland.lab)
    participant OW as Open WebUI
    participant NG as nemo-guardrails (/v1/chat/completions)
    participant NR as NeMo rails (LLMRails)
    participant OLL as Ollama gpt-oss:20b (rogueone)
    U->>OW: pick "weyland-operator", send a message
    OW->>NG: POST /v1/chat/completions {model: weyland-operator, messages}
    NG->>NR: LLMRails.generate(messages)
    NR->>OLL: self check input — is this a lab-ops request? (LLM judge)
    OLL-->>NR: Yes (block) | No (allow)
    alt off-topic / jailbreak (block)
        NR-->>NG: "I'm the weyland lab operator — I only handle lab operations…"
    else on-topic (allow)
        NR->>OLL: main completion
        OLL-->>NR: answer
        NR-->>NG: answer
    end
    NG-->>OW: OpenAI chat.completion (streamed)
    OW-->>U: guarded response
```
