"""weyland-mcp-compositor — B17+B19 Phase 3. A FastMCP proxy that aggregates the read-only MCP fleet + the
tool-server's read `/mcp` into ONE MCP endpoint, tools namespaced per upstream (`grafana_*`, `trino_*`, `context_*`…).
Fronted by weyland-mcp-gateway (the single auth + actor-injection point).

ACTS ARE NOT HERE. Only read surfaces are composed. The tool-server's `/mcp-act` (+ `/pipeline/trigger`, `/evals/*`)
stay on the direct gateway→tool-server path where `policy.gate` + the anti-spoof AuthorizationPolicy govern them.

create_proxy(MCPConfig) mounts each server with its config key as the tool prefix. Per-upstream transport is declared
(streamable-http vs sse). Upstreams + their read-only allowlists live in config.py (unit-tested). Each upstream URL is
env-overridable; **set its URL env to empty to SKIP it** (for bisecting a backend that won't handshake)."""
import dataclasses
import os

from fastmcp.server import create_proxy

from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware

from config import build_servers, governed_writes_enabled, is_blocked, rewrite_arguments

servers = build_servers(os.environ)
print(f"[compositor] mounting upstreams: {sorted(servers)}", flush=True)


class ReadOnlyAllowlist(Middleware):
    """B182 — a read-only upstream's tools reach the fleet only if allowlisted (config.READ_ONLY): hidden from
    tools/list AND refused on call, so a client that knows a write tool's name still cannot call it. Allowed calls get
    config.rewrite_arguments (a memory search becomes semantic). The context is a frozen dataclass — replace, not set."""

    async def on_list_tools(self, context, call_next):
        return [t for t in await call_next(context) if not is_blocked(t.name, servers)]

    async def on_call_tool(self, context, call_next):
        if is_blocked(context.message.name, servers):
            raise ToolError(f"{context.message.name} is not allowed through the read-only fleet")
        args = context.message.arguments or {}
        new = rewrite_arguments(context.message.name, args, servers)
        if new is not args:
            context = dataclasses.replace(context, message=context.message.model_copy(update={"arguments": new}))
        return await call_next(context)


app = create_proxy({"mcpServers": servers}, name="weyland-mcp-compositor")
app.add_middleware(ReadOnlyAllowlist())

# B256 (2026-11-23) walking skeleton: identity-checked, provenance-stamped writes (governed_write.py). Only on the memory
# compositor with GOVERNED_WRITE=1: its NetworkPolicy admits the gateway alone, so X-Forwarded-User / -Consumer were set
# by the gateway from a validated token. Design: docs/design/shared-context-design.md.
if governed_writes_enabled(os.environ):
    from datetime import datetime, timezone

    from fastmcp.server.dependencies import get_http_headers

    import governed_write as gw
    from governed_store import BasicMemoryStore, RoutingStore, client_call, person_urls

    # The shared layers on the shared server; each person's layer on their OWN server (PERSON_MEMORY_URLS).
    _store = RoutingStore(BasicMemoryStore(client_call(os.environ["MEMORY_URL"])),
                          {name: BasicMemoryStore(client_call(url)) for name, url in person_urls(os.environ).items()})
    print("[compositor] governed writes ON (governed_write_note, governed_read_note)", flush=True)

    @app.tool(name="governed_write_note")
    async def governed_write_note(directory: str, title: str, content: str, operation: str, source: str,
                                  expected_sha256: str | None = None, supersedes: str | None = None) -> dict:
        """Write to the shared agent memory as YOURSELF: the gateway's identity is checked against the layer's rights
        and stamped into the note's frontmatter (created_by / updated_by, author_kind, on_behalf_of, source, times).
        directory: "" (project memory), "task/<item>" or "person/<name>". operation: "create" (fails if the note
        exists), "append" (adds to it), "replace" (needs expected_sha256 from governed_read_note; refused if the note
        changed since), or "supersede" (a fact turned out wrong: writes this note as the correction of `supersedes`,
        another note's title in the same directory, which is marked invalid and linked, never deleted). source: the
        B-number, incident or session this came from. A task's "handoff" note must have the sections ## State
        (working | input-required | done), ## Done, ## Verified, ## Open, ## Next. Content must not carry frontmatter
        or secrets."""
        identity = gw.identity_from_headers(get_http_headers())
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        out = await gw.governed_write(_store, identity, directory=directory, title=title, content=content,
                                      operation=operation, source=source, expected_sha256=expected_sha256, now=now,
                                      supersedes=supersedes)
        print(gw.audit_line(identity, operation, directory, title, out), flush=True)
        if not out.ok:
            raise ToolError(out.reason)
        return {"result": out.reason, "path": out.path}

    @app.tool(name="governed_read_note")
    async def governed_read_note(directory: str, title: str) -> dict:
        """Read one note with its SHA-256, the version a "replace" must send. directory: "" (project memory),
        "task/<item>" or "person/<name>" (readable only by that person and their agents)."""
        identity = gw.identity_from_headers(get_http_headers())
        path, why = gw.read_path(identity, directory, title)   # layer, person rule and title checked together
        if why:
            raise ToolError(why)
        project, spath, _ = gw.store_location(directory, title)   # a person's notes are their own project
        raw = await _store.read_raw(spath, project=project)
        if raw is None:
            raise ToolError(f"{path} does not exist")
        return {"path": path, "sha256": gw.sha256_of(raw), "text": raw}

if __name__ == "__main__":
    app.run(transport="http", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
