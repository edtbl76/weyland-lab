# C4 Component — rogueone (external)

Level 3: components on the rogueone laptop. rogueone is an EXTERNAL system to weyland (separate physical machine on the same LAN). See [c4-context.md](c4-context.md) for system context.

```mermaid
C4Component
    title rogueone (.230) — Components (External System)

    Person_Ext(user, "Edward", "Primary dev workstation operator")
    System_Ext(anthropic, "Anthropic API", "Claude models")
    Container_Ext(tool_server, "weyland-tool-server", "MCP /mcp :30080")
    Container_Ext(dagster, "Dagster (mother)", "SSH reads Obsidian vault")

    Container_Boundary(rogueone_sys, "rogueone — laptop (.230) · RTX 5000 Ada 16GB") {

        Component(claude_code, "Claude Code", "CLI (claude)", "Primary dev assistant. MCP client: registered weyland system-view MCP (url: http://192.168.1.243:30080/mcp, transport: http). Validated 2026-06-14 — status tool returns live system state. Reasoning brain: Anthropic API (cloud). Project: /home/edwardmangini/IdeaProjects/weyland")

        Component(vllm, "vLLM", "Python / CUDA", "GPU LLM serving. On-demand (not always-on). OpenAI-compatible /v1 :8000. RTX 5000 Ada 16GB VRAM. Serves Qwen models. Too small for 30B@4bit; sweet spot <=13B for speed.")

        Component(obsidian, "Obsidian Vault", "Markdown files", "Source notes and documentation. Current RAG source: weyland.md (single file, gitignored). B25 will replace with git-pull of the full docs/ tree from the weyland repo, retiring this as the RAG source.")

        Component(weyland_repo, "weyland git repo", "git / IdeaProjects", "/home/edwardmangini/IdeaProjects/weyland. The canonical source of truth for all infrastructure, k8s manifests, services, and documentation. B25 target: Dagster ingests docs/ tree from this repo via git.")
    }

    Rel(user, claude_code, "primary dev interface")
    Rel(user, vllm, "on-demand GPU inference")
    Rel(user, obsidian, "writes lab notes")
    Rel(claude_code, tool_server, "MCP /mcp (status, context_search, context_ask, list_models)")
    Rel(claude_code, anthropic, "LLM reasoning (cloud)")
    Rel(dagster, obsidian, "SSH/SFTP reads weyland.md (paramiko, pinned host key) — B25 will retire this path")
    Rel(dagster, weyland_repo, "B25 target: git clone/pull docs/ tree for RAG ingestion")
```
