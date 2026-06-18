# C4 Container — Weyland

Level 2: deployable containers inside the weyland system boundary. For external context see [c4-context.md](c4-context.md). For component detail see the component files linked below.

**Component diagrams:** [mother k3s](c4-component-mother.md) · [hermes CT](c4-component-hermes.md) · [ollama CT](c4-component-ollama.md) · [whisper CT](c4-component-whisper.md) · [openclaw VM](c4-component-openclaw.md) · [rogueone](c4-component-rogueone.md)

```mermaid
C4Container
    title Weyland — Container Diagram

    Person(user, "Edward", "Lab operator")
    System_Ext(telegram, "Telegram", "Cloud messaging platform")
    System_Ext(anthropic, "Anthropic API", "Claude cloud models (OpenClaw only — deprioritized)")
    System_Ext(hostedmodels, "Gemini / OpenRouter", "Free-tier hosted LLMs — via mother LiteLLM gateway")
    System_Ext(github, "GitHub", "weyland-lab repo — RAG source (B25b) + roadmap backlog")
    System_Ext(rogueone, "rogueone", "External laptop: Claude Code, vLLM")

    System_Boundary(weyland, "weyland — MS-A2 Proxmox (.232)") {

        Container(mother, "mother VM", "k3s / Kubernetes", "Shared AI platform: all k3s workloads (tool-server, RAG backends, Dagster, UIs, observability, storage, ingress), wrapped in an Istio service mesh (mTLS). vm-101 · .243. See c4-component-mother.md")

        Container(hermes, "hermes CT", "Python / systemd", "Primary AI agent. qwen3-coder brain via Ollama, MCP client of tool-server, Telegram front door. CT 104 · .247. See c4-component-hermes.md")

        Container(ollama_ct, "ollama CT", "Ollama / llama.cpp", "CPU LLM serving. 6 GGUF models, num_thread 8, one model resident. CT 102 · .244. See c4-component-ollama.md")

        Container(whisper_ct, "whisper CT", "whisper.cpp + Python shim", "CPU speech-to-text. native /inference + OpenAI-compatible shim. CT 103 · .246. See c4-component-whisper.md")

        Container(openclaw_vm, "openclaw VM", "Node.js / Docker", "DEPRIORITIZED (B28). OpenClaw gateway: Claude CLI brain, Telegram bot, Tavily search. vm-100 · .169. See c4-component-openclaw.md")
    }

    Rel(user, hermes, "Telegram DM (allowlisted)")
    Rel(user, mother, "browser UIs: chat.weyland.lab, dagster.weyland.lab, grafana.weyland.lab etc.")
    Rel(user, openclaw_vm, "Telegram DM — DEPRIORITIZED")
    Rel(telegram, hermes, "inbound DM delivery")
    Rel(telegram, openclaw_vm, "inbound DM — DEPRIORITIZED")
    Rel(hermes, ollama_ct, "LLM inference /v1 (reasoning)")
    Rel(hermes, mother, "system-view MCP /mcp (read-only tools)")
    Rel(mother, ollama_ct, "RAG generation + eval judging /v1")
    Rel(mother, whisper_ct, "STT /v1/audio/transcriptions")
    Rel(mother, github, "Dagster git-pulls docs/ + nodes/ for RAG (B25b)")
    Rel(mother, hostedmodels, "LiteLLM gateway egress + model_catalog fetch")
    Rel(hermes, mother, "planning turns via LiteLLM gateway /v1 (Gemini)")
    Rel(hermes, github, "roadmap-sync pulls backlog.md (6h cron)")
    Rel(openclaw_vm, mother, "RAG context /context/search — DEPRIORITIZED")
    Rel(openclaw_vm, anthropic, "Claude CLI reasoning — DEPRIORITIZED")
    Rel(rogueone, mother, "Claude Code MCP /mcp (read-only tools)")
    Rel(hermes, telegram, "agent replies")
    Rel(mother, telegram, "Alertmanager notifications")
```
