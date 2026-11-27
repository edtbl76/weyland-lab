# Golden path — Python / litestar. Multi-stage, non-root, minimal. buildkit → registry.weyland.lab/golden-python-litestar.
FROM python:3.12-slim AS deps
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim
WORKDIR /app
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser
COPY --from=deps /install /usr/local
# v2_smoke.py / items_store.py / items_backends.py: synced from golden-paths-shared/python (B261).
COPY main.py smoke.py v2_smoke.py items_store.py items_backends.py .
USER 10001
EXPOSE 8080
# main:serve is an app factory: config validated and tracing set up when uvicorn starts (deep contract v2, B261).
CMD ["uvicorn", "--factory", "main:serve", "--host", "0.0.0.0", "--port", "8080"]
