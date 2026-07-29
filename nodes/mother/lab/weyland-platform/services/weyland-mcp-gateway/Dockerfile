FROM python:3.12-slim

WORKDIR /app

# Thin proxy — Starlette + uvicorn + httpx (streaming reverse-proxy) + PyJWT[crypto] (RS256 JWKS validation).
RUN pip install --no-cache-dir \
    starlette \
    "uvicorn[standard]" \
    httpx \
    "pyjwt[crypto]"

COPY app.py /app/app.py

RUN useradd -u 10001 -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
