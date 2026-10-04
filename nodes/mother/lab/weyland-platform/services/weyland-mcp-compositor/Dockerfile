# weyland-mcp-compositor — FastMCP proxy aggregating the read-only MCP fleet behind one endpoint (B17+B19 Phase 3).
FROM python:3.12-slim
# Pinned (2026-10-03): this used to 'pip install fastmcp' unpinned. requirements.txt is frozen from requirements.in.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
RUN useradd -u 10001 -m app
USER 10001
COPY app.py config.py /app/
WORKDIR /app
ENTRYPOINT ["python", "app.py"]
