# datahub-mcp — the OFFICIAL acryldata/mcp-server-datahub packaged for in-cluster HTTP transport. Acryl publishes the
# server only as a PyPI package (uvx, stdio); there's no official HTTP container image, so we build a thin one. FastMCP-
# based (like neo4j-mcp). Read-only by default — mutation tools are opt-in via TOOLS_IS_MUTATION_ENABLED (left unset).
FROM python:3.12-slim
# PINNED (was unpinned — froze at 0.6.0 / mcp 1.29.0). mcp 1.29 let a client-disconnect ClosedResourceError
# propagate to the serving TaskGroup and crash the whole server (found 2026-09-22 -> 946 restarts). mcp 1.30.0
# isolates session failures (shielded cancel scope + session-level except), verified by source-diff of
# streamable_http_manager.py 1.29->1.30. KEEP mcp-server-datahub AT 0.6.0: 0.7.x dropped `http` from
# `--transport` (only stdio|sse now), which breaks the `--transport http` manifest + the compositor's http
# upstream; 0.6.0 keeps http AND its dep range resolves mcp to 1.30.0. Runtime-verified in docker that
# `mcp-server-datahub --transport http` starts on this exact combo (past arg-parse + mcp-1.30 import).
RUN pip install --no-cache-dir 'mcp-server-datahub==0.6.0' 'mcp==1.30.0'
RUN useradd -u 10001 -m app
USER 10001
ENTRYPOINT ["mcp-server-datahub"]
