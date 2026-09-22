# datahub-mcp — the OFFICIAL acryldata/mcp-server-datahub packaged for in-cluster HTTP transport. Acryl publishes the
# server only as a PyPI package (uvx, stdio); there's no official HTTP container image, so we build a thin one. FastMCP-
# based (like neo4j-mcp). Read-only by default — mutation tools are opt-in via TOOLS_IS_MUTATION_ENABLED (left unset).
FROM python:3.12-slim
# PINNED (was unpinned — froze at 0.6.0 / mcp 1.29.0). mcp 1.29 let a client-disconnect ClosedResourceError
# propagate to the serving TaskGroup and crash the whole server (found 2026-09-22: the compositor's ~3/sec
# /mcp fan-out tore sessions down mid-flight -> 946 restarts). mcp 1.30.0 isolates session failures
# (shielded cancel scope + session-level `except Exception`), so a disconnect kills only that session. Verified
# by source-diff of streamable_http_manager.py between 1.29.0 and 1.30.0. Bump both together and re-verify.
RUN pip install --no-cache-dir mcp-server-datahub==0.7.1 'mcp==1.30.0'
RUN useradd -u 10001 -m app
USER 10001
ENTRYPOINT ["mcp-server-datahub"]
