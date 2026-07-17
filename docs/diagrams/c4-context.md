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

## Same view in D2 (B64 evaluation)

Rendered to SVG at build time by `mkdocs-d2-plugin` (dagre layout). This block is the spike proof — compare legibility/layout with the Mermaid above. If this reads well, the structural diagrams (C4 + flowcharts) migrate to D2; the sequence diagrams stay in Mermaid.

```d2
# B64 spike — C4 context authored in D2. Compare with the Mermaid above.
direction: right

classes: {
  person: {
    shape: person
    style: { fill: "#08427b"; stroke: "#052e56"; font-color: "#ffffff" }
  }
  core: {
    style: { fill: "#1168bd"; stroke: "#0b4884"; font-color: "#ffffff" }
  }
  ext: {
    style: { fill: "#8b8b8b"; stroke: "#5f5f5f"; font-color: "#ffffff" }
  }
}

user: "Edward — lab operator (sole user)" { class: person }
weyland: "weyland — home AI lab (MS-A2): LLM inference, RAG, STT, eval, observability, object storage, agents. LAN-only." { class: core }
rogueone: "rogueone — RTX 5000 Ada laptop: vLLM GPU, dev + Claude Code, native Ray edge worker → mother's head" { class: ext }
telegram: "Telegram — inbound DMs to Hermes, Alertmanager alerts out" { class: ext }
github: "GitHub — weyland-lab repo: RAG corpus (docs/+nodes/) + roadmap backlog" { class: ext }
hostedmodels: "Gemini / OpenRouter — free-tier hosted LLMs via LiteLLM ($0)" { class: ext }
anthropic: "Anthropic API — Claude for Claude Code on rogueone (Hermes-Claude declined)" { class: ext }
tavily: "Tavily — cloud web search (OpenClaw, deprioritized B28)" { class: ext }
hf: "Hugging Face Hub — model weights (bge-small + GGUF) at build time" { class: ext }

user -> weyland: "Telegram DM, browser UIs, Claude Code"
user -> rogueone: "develops on / operates from"
weyland -> telegram: "Hermes replies + alerts"
telegram -> weyland: "inbound DMs → Hermes"
rogueone -> weyland: "MCP /mcp; vLLM on-demand"
rogueone -> anthropic: "Claude Code brain"
weyland -> github: "Dagster git-pull (RAG); roadmap-sync"
weyland -> hostedmodels: "LiteLLM: Hermes planning + model_catalog"
weyland -> tavily: "web search via OpenClaw"
weyland -> hf: "model weight pulls at setup"
```

