# nemo-guardrails (B115 Dialog layer) — NeMo Guardrails ISOLATED in its own image (its langchain/embedding dep tree is
# heavy and version-opinionated, like guardrails-ai). FastAPI wraps the NeMo library and exposes a plain OpenAI
# /v1/chat/completions that Open WebUI adds as a connection.
# Two stages (2026-10-17, B220): build-essential compiles NeMo's source-only transitive deps (annoy, …), but it also
# installs linux-libc-dev (kernel headers), which carried 5 HIGH advisories with no Debian fix into the RUNTIME image.
# The builder compiles into /install; the runtime image gets only the installed packages — no compiler, no headers.
FROM python:3.11-slim AS build
# git for pip VCS installs if pulled.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential git \
    && rm -rf /var/lib/apt/lists/*
# 2026-10-16: pinned. requirements.txt is the full frozen set of the image this replaced, so a rebuild can no longer
# drift and the source scanners can read it.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r /tmp/requirements.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=build /install /usr/local

COPY app.py /app/app.py
COPY config/ /app/config/

RUN useradd -u 10001 -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
