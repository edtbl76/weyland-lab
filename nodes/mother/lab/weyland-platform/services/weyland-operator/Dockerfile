FROM python:3.12-slim

WORKDIR /app

# No torch / no HF embedder / no store clients — the operator reasons over the tool-server via HTTP, so it stays
# light. `langchain` (full package) is required by mlflow.langchain.autolog(); langgraph + langchain-openai drive the
# ReAct loop against Ollama.
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    httpx \
    psycopg2-binary \
    prometheus-client \
    langgraph \
    langchain \
    langchain-openai \
    langchain-mcp-adapters==0.3.1 \
    mcp==1.24.0 \
    mlflow

COPY tools.py agent.py guard.py telegram.py session.py ingress.py act.py prompts.py fleet.py realm.py app.py /app/

RUN useradd -u 10001 -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
