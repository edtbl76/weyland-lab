"""MCP tools for an agent — its slice of the Bifrost VK surface, filtered by subsystem.

The `coding-agents` VK aggregates the 232-tool surface behind Bifrost `/mcp`. We load them once via
langchain-mcp-adapters (header `x-bf-vk`), then hand each agent only the tools whose names match its `tool_prefixes`
(e.g. Verðandi → `grafana`, Sága → `trino`/`postgres`). Fail-safe: no VK or an unreachable gateway → the agent runs
tool-less (it can still reason and answer). The MCP session is per-call (stateless), matching the operator's fleet loader."""
import asyncio

import httpx

from budget import is_free_only
from config import BIFROST_MCP_URL, BIFROST_VK
from obs import current_session, log


class _SessionAwareClient(httpx.AsyncClient):
    """Adds the current dispatch session as `x-bf-session-id` to every request, read at send time. `send` is the one
    path both `request()` and `stream()` take, so the MCP transport's streamed calls carry it too."""

    async def send(self, request: httpx.Request, **kwargs) -> httpx.Response:
        sid = current_session()
        if sid:
            request.headers["x-bf-session-id"] = sid
        return await super().send(request, **kwargs)


def session_aware_client(headers: dict | None = None, timeout: httpx.Timeout | None = None,
                         auth: httpx.Auth | None = None) -> httpx.AsyncClient:
    """httpx client for the Bifrost MCP connection (an `McpHttpClientFactory`). The tools are loaded once per process
    with fixed headers, so the dispatch's session id is added per request: Bifrost's Agent Logs then join a
    conversation's tool calls to it (`x-bf-session-id`, B249, 2026-11-19). No session, no header."""
    return _SessionAwareClient(headers=headers, timeout=timeout if timeout is not None else httpx.Timeout(30.0),
                               auth=auth, follow_redirects=True)

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
                        "headers": {"x-bf-vk": BIFROST_VK}, "httpx_client_factory": session_aware_client},
        })
        _all_tools = await client.get_tools()
        log(f"loaded {len(_all_tools)} VK tools from Bifrost")
    except Exception as exc:
        log(f"tool load failed — agents run tool-less: {exc}")
        _all_tools = []
    return _all_tools


# Tools that spend money per call whatever the model lane (Perplexity bills its provider key). A free-only request
# promises to spend nothing, so it never gets them (B253, 2026-11-20; before, a free-only run reaching Ratatoskr could
# still call Perplexity). The graph caches are keyed by free-only, so a free-only graph is built without them.
PAID_TOOL_PREFIXES = ("perplexity",)


async def tools_for(prefixes: tuple) -> list:
    """Return the subset of VK tools whose names contain any of `prefixes` (substring match, robust to namespacing),
    minus the paid tools inside a free-only request."""
    if not prefixes:
        return []
    everything = await _load_all()
    pref = tuple(p.lower() for p in prefixes)
    picked = [t for t in everything if any(p in t.name.lower() for p in pref)]
    if is_free_only():
        picked = [t for t in picked if not any(p in t.name.lower() for p in PAID_TOOL_PREFIXES)]
    return picked


def tools_for_sync(prefixes: tuple) -> list:
    """Sync convenience for build-time wiring — safe to call before the event loop is running."""
    try:
        return asyncio.run(tools_for(prefixes))
    except RuntimeError:
        # already inside a loop (shouldn't happen at build time) — skip tools rather than crash
        return []
