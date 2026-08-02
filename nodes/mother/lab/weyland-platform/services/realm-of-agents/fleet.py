"""MCP tools for an agent — its slice of the Bifrost VK surface, filtered by subsystem.

The `coding-agents` VK aggregates the 232-tool surface behind Bifrost `/mcp`. We load them once via
langchain-mcp-adapters (header `x-bf-vk`), then hand each agent only the tools whose names match its `tool_prefixes`
(e.g. Verðandi → `grafana`, Sága → `trino`/`postgres`). Fail-safe: no VK or an unreachable gateway → the agent runs
tool-less (it can still reason and answer). The MCP session is per-call (stateless), matching the operator's fleet loader."""
import asyncio

from config import BIFROST_MCP_URL, BIFROST_VK
from obs import log

_all_tools: list | None = None   # lazy, process-wide cache of the full VK tool set


async def _load_all() -> list:
    global _all_tools
    if _all_tools is not None:
        return _all_tools
    if not BIFROST_VK:
        _all_tools = []
        return _all_tools
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
        client = MultiServerMCPClient({
            "bifrost": {"transport": "streamable_http", "url": BIFROST_MCP_URL,
                        "headers": {"x-bf-vk": BIFROST_VK}},
        })
        _all_tools = await client.get_tools()
        log(f"loaded {len(_all_tools)} VK tools from Bifrost")
    except Exception as exc:
        log(f"tool load failed — agents run tool-less: {exc}")
        _all_tools = []
    return _all_tools


async def tools_for(prefixes: tuple) -> list:
    """Return the subset of VK tools whose names contain any of `prefixes` (substring match, robust to namespacing)."""
    if not prefixes:
        return []
    everything = await _load_all()
    pref = tuple(p.lower() for p in prefixes)
    return [t for t in everything if any(p in t.name.lower() for p in pref)]


def tools_for_sync(prefixes: tuple) -> list:
    """Sync convenience for build-time wiring — safe to call before the event loop is running."""
    try:
        return asyncio.run(tools_for(prefixes))
    except RuntimeError:
        # already inside a loop (shouldn't happen at build time) — skip tools rather than crash
        return []
