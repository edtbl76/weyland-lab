FROM python:3.12-slim

WORKDIR /app

# Thin proxy — Starlette + uvicorn + httpx (streaming reverse-proxy) + PyJWT[crypto] (RS256 JWKS validation).
# PINNED (2026-10-04): requirements.txt is the frozen, pip-audited set — the deps were unpinned here, the same drift
# risk that broke Dagster (an unpinned base pulled a breaking release). See requirements.in.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app.py /app/app.py

RUN useradd -u 10001 -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
