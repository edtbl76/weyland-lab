FROM python:3.12-slim

WORKDIR /app

# No torch / no HF embedder / no store clients — the operator reasons over the tool-server via HTTP, so it stays
# light. `langchain` (full package) is required by mlflow.langchain.autolog(); langgraph + langchain-openai drive the
# ReAct loop against Ollama.
# Pinned (2026-10-02): this used to `pip install` its packages UNPINNED — the class that took Dagster down on
# 2026-10-01. requirements.txt is frozen from requirements.in (see its header for how to regenerate).
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY tools.py agent.py guard.py telegram.py session.py ingress.py act.py prompts.py fleet.py realm.py decide.py incidents.py app.py /app/

RUN useradd -u 10001 -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
