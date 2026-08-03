# nemo-guardrails (B115 Dialog layer) — NeMo Guardrails ISOLATED in its own image (its langchain/embedding dep tree is
# heavy and version-opinionated, like guardrails-ai). FastAPI wraps the NeMo library and exposes a plain OpenAI
# /v1/chat/completions that Open WebUI adds as a connection.
FROM python:3.11-slim

WORKDIR /app

# build-essential covers any source-only transitive dep in NeMo's tree; git for pip VCS installs if pulled.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    nemoguardrails

COPY app.py /app/app.py
COPY config/ /app/config/

RUN useradd -u 10001 -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
