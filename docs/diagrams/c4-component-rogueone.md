# C4 Component — rogueone (external)

Level 3: components on the rogueone laptop. rogueone is an EXTERNAL system to weyland (separate physical machine on the same LAN). See [c4-context.md](c4-context.md) for system context.

```mermaid
C4Component
    title rogueone (.230) — Components (External System)

    Person_Ext(user, "Edward", "Primary dev workstation operator")
    System_Ext(anthropic, "Anthropic API", "Claude models")
    System_Ext(github, "GitHub", "weyland-lab repo — RAG source")
    Container_Ext(tool_server, "weyland-tool-server", "MCP /mcp :30080")
    Container_Ext(dagster, "Dagster (mother)", "git-pulls docs/+nodes/ from GitHub (B25b)")

    Container_Boundary(rogueone_sys, "rogueone — laptop (.230) · RTX 5000 Ada 16GB") {

        Component(claude_code, "Claude Code", "CLI (claude)", "Primary dev assistant. MCP client: registered weyland system-view MCP (url: http://192.168.1.243:30080/mcp, transport: http). Validated 2026-06-14 — status tool returns live system state. Reasoning brain: Anthropic API (cloud). Project: /home/edwardmangini/IdeaProjects/weyland")

        Component(vllm, "vLLM", "Python / CUDA", "GPU LLM serving. On-demand (not always-on). OpenAI-compatible /v1 :8000. RTX 5000 Ada 16GB VRAM. Serves Qwen models. Too small for 30B@4bit; sweet spot <=13B for speed.")

        Component(obsidian, "Obsidian Vault", "Markdown files", "Personal notes/docs. RETIRED as RAG source (B25b) — the RAG now ingests the GitHub repo (docs/ + nodes/) via Dagster git-pull, not this vault.")

        Component(weyland_repo, "weyland git repo", "git / IdeaProjects", "/home/edwardmangini/IdeaProjects/weyland. Canonical source of truth for all infra, k8s manifests, services, and docs. Pushed to GitHub, where Dagster git-pulls docs/ + nodes/ for the RAG (B25b — done).")
    }

    Rel(user, claude_code, "primary dev interface")
    Rel(user, vllm, "on-demand GPU inference")
    Rel(user, obsidian, "writes lab notes")
    Rel(claude_code, tool_server, "MCP /mcp (status, context_search, context_ask, list_models)")
    Rel(claude_code, anthropic, "LLM reasoning (cloud)")
    Rel(weyland_repo, github, "git push")
    Rel(dagster, github, "git-pull docs/ + nodes/ for RAG ingestion (B25b)")
```
