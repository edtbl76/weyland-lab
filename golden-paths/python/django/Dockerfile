# Golden path — Python / django. Multi-stage, non-root, minimal. buildkit → registry.weyland.lab/golden-python-django.
FROM python:3.12-slim AS deps
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim
WORKDIR /app
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser
COPY --from=deps /install /usr/local
# items_store.py / items_backends.py: the shared store, synced from golden-paths-shared/python (B261).
COPY main.py smoke.py v2_smoke.py items_store.py items_backends.py .
USER 10001
EXPOSE 8080
# main:serve() validates config, opens the store and returns the WSGI app (deep contract v2, B261).
CMD ["gunicorn","-b","0.0.0.0:8080","main:serve()"]
