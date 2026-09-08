# Golden path — Python / FastAPI. Multi-stage, non-root, minimal. buildkit builds to
# registry.weyland.lab/golden-python-fastapi. The ephemeral Job runs this image, hits /ready + /hello,
# and exits. A scaffolded real service inherits this Dockerfile.
FROM python:3.12-slim AS deps
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim
WORKDIR /app
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser
COPY --from=deps /install /usr/local
COPY main.py smoke.py .
USER 10001
EXPOSE 8080
# readinessProbe target: GET /ready (the SMOKE gate + the ephemeral Job assert this).
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
