# weyland-mcp-compositor — FastMCP proxy aggregating the read-only MCP fleet behind one endpoint (B17+B19 Phase 3).
FROM python:3.12-slim
RUN pip install --no-cache-dir fastmcp
RUN useradd -u 10001 -m app
USER 10001
COPY app.py /app/app.py
WORKDIR /app
ENTRYPOINT ["python", "app.py"]
