FROM python:3.12-slim

WORKDIR /app

# No torch / embedder — every agent reasons via LiteLLM (wl-* lanes) and reaches tools over MCP (Bifrost VK), so the pod
# stays light. langgraph + langchain-openai drive each ReAct loop; langchain-mcp-adapters loads the VK tool surface.
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    httpx \
    prometheus-client \
    langgraph \
    langchain \
    langchain-openai \
    langchain-mcp-adapters==0.3.1 \
    mcp==1.24.0

COPY config.py roster.py prompts.py llm.py fleet.py agents.py realms.py router.py cards.py app.py /app/

RUN useradd -u 10001 -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
