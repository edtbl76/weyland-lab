# C4 Context — Weyland

Level 1: weyland in the world. Shows system boundaries and external actors. For internal containers see [c4-container.md](c4-container.md).

```mermaid
C4Context
    title Weyland System Context

    Person(user, "Edward", "Lab operator — sole user of the system")

    System(weyland, "weyland", "Home AI lab running on a Minisforum MS-A2. Local LLM inference, RAG, STT, eval harness, observability, object storage, and AI agents. LAN-only, no public access.")

    System_Ext(rogueone, "rogueone", "External laptop (RTX 5000 Ada 16GB, 128GB RAM). GPU inference via vLLM, dev workstation, Claude Code CLI, and remote model training (native Ray edge worker → mother's Ray head).")

    System_Ext(telegram, "Telegram", "Cloud messaging platform. Delivers inbound DMs to the Hermes agent and receives Alertmanager notifications.")
    System_Ext(github, "GitHub", "weyland-lab repo. RAG corpus source (docs/ + nodes/, B25b) and the roadmap backlog Hermes mirrors.")
    System_Ext(hostedmodels, "Gemini / OpenRouter", "Free-tier hosted LLMs via the LiteLLM gateway on mother. Hermes planning brain + model catalog. API-key, $0.")
    System_Ext(anthropic, "Anthropic API", "Cloud API. Claude models — used by Claude Code on rogueone. (B26 Hermes-Claude brain DECLINED — ToS/cost; Hermes uses free hosted models instead.) Metered, off-LAN.")
    System_Ext(tavily, "Tavily", "Cloud web search API. Used by OpenClaw (deprioritized, B28).")
    System_Ext(hf, "Hugging Face Hub", "Model weight source. bge-small-en-v1.5 embedding model pulled at build time. GGUF models pulled during CT setup.")

    Rel(user, weyland, "operates via Telegram DM, browser UIs, and Claude Code")
    Rel(user, rogueone, "develops on and operates from")
    Rel(weyland, telegram, "Hermes agent replies + Alertmanager alerts")
    Rel(telegram, weyland, "inbound DMs routed to Hermes agent")
    Rel(rogueone, weyland, "Claude Code queries MCP /mcp; vLLM on-demand inference")
    Rel(rogueone, anthropic, "Claude Code reasoning brain")
    Rel(weyland, github, "Dagster git-pulls docs/+nodes/ (RAG); Hermes roadmap-sync pulls backlog.md")
    Rel(weyland, hostedmodels, "LiteLLM gateway: Hermes planning + model_catalog (Gemini/OpenRouter)")
    Rel(weyland, tavily, "web search via OpenClaw (deprioritized B28)")
    Rel(weyland, hf, "model weight pulls at setup time only")
```

