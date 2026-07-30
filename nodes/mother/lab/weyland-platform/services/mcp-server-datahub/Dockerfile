# datahub-mcp — the OFFICIAL acryldata/mcp-server-datahub packaged for in-cluster HTTP transport. Acryl publishes the
# server only as a PyPI package (uvx, stdio); there's no official HTTP container image, so we build a thin one. FastMCP-
# based (like neo4j-mcp). Read-only by default — mutation tools are opt-in via TOOLS_IS_MUTATION_ENABLED (left unset).
FROM python:3.12-slim
RUN pip install --no-cache-dir mcp-server-datahub
RUN useradd -u 10001 -m app
USER 10001
ENTRYPOINT ["mcp-server-datahub"]
