# C4 Component — openclaw VM (vm-100)

Level 3: components inside the OpenClaw VM. **DEPRIORITIZED (B28)** — running but not the active agent path. See [c4-container.md](c4-container.md) for context.

```mermaid
C4Component
    title openclaw VM vm-100 (.169) — Components (DEPRIORITIZED — B28)

    Person_Ext(user, "Edward", "Telegram DM — deprioritized path")
    System_Ext(telegram, "Telegram", "Messaging platform")
    System_Ext(anthropic, "Anthropic API", "Claude CLI reasoning brain")
    System_Ext(tavily, "Tavily", "Web search API")
    Container_Ext(tool_server, "weyland-tool-server", "RAG context /context/search")

    Container_Boundary(openclaw_vm, "openclaw VM vm-100 (.169) — Node.js / Docker (DEPRIORITIZED)") {

        Component(gateway, "OpenClaw Gateway", "Node.js / Docker (openclaw-openclaw-gateway-1)", "Main gateway process. Manages channels (Telegram), agent routing, MCP runtime, plugin/skill registry. Config: /home/node/.openclaw/openclaw.json (manage via CLI only — never hand-edit). Currently degraded: MCP not surfacing to brain, no command owner set, claude-cli auth expiring, memory search broken (OpenAI key missing).")

        Component(claude_cli, "Claude CLI", "claude binary /usr/local/bin/claude", "Primary reasoning brain. Anthropic OAuth auth (8h expiry — needs periodic re-auth). Headless mode for gateway. Workspace: $OPENCLAW_HOME/.claude/")

        Component(tavily_plugin, "Tavily Plugin", "openclaw plugin", "Web search capability. API key in openclaw.json (plaintext — security finding from openclaw doctor). Enabled but deprioritized.")

        Component(mcp_weyland, "weyland MCP registration", "openclaw.json mcp_servers", "Registered: url http://192.168.1.243:30080/mcp, transport streamable-http. Currently NOT surfacing to agent brain (gateway MCP runtime stuck reconnecting). Probe confirms 4 tools available at transport level.")

        Component(openclaw_mcp, "openclaw MCP server", "openclaw mcp serve", "Exposes openclaw's own capabilities (session, memory, cron, goals, web search) over MCP stdio.")
    }

    Rel(telegram, gateway, "inbound DMs")
    Rel(gateway, claude_cli, "reasoning turns")
    Rel(claude_cli, anthropic, "Claude API (8h OAuth token)")
    Rel(gateway, tavily_plugin, "web search requests")
    Rel(tavily_plugin, tavily, "search queries")
    Rel(gateway, mcp_weyland, "MCP tool calls (currently broken)")
    Rel(mcp_weyland, tool_server, "MCP Streamable HTTP (transport OK, brain integration broken)")
    Rel(gateway, telegram, "agent replies")
```
