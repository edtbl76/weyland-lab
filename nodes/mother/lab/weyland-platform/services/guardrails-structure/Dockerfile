# guardrails-structure (B115 Structure layer) — Guardrails AI ISOLATED in its own image. It can't co-install with the
# Dagster/dbt/huggingface stack (guardrails-ai pins click<=8.2.0 vs the stack's click>=8.4.2), so it lives here alone,
# where its dep tree (litellm + friends) resolves freely. FastAPI front door; the eval judge POSTs its raw JSON here.
FROM python:3.11-slim

WORKDIR /app

# Only the guard's needs — guardrails-ai pulls litellm/openai/etc. transitively; no pins to fight in this image.
# 2026-10-16: pinned. requirements.txt is the full frozen set of the image this replaced, so a rebuild can no longer
# drift and the source scanners can read it.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY app.py /app/app.py

# Non-root (uid 10001, matching the other weyland services).
RUN useradd -u 10001 -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
