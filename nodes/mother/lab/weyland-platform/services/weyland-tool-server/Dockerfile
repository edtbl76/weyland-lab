FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn psycopg2-binary sentence-transformers

COPY main.py /app/main.py

ENV WEYLAND_DB_HOST=weyland-postgres.weyland.svc.cluster.local
ENV WEYLAND_DB_PORT=5432
ENV WEYLAND_DB_NAME=weyland
ENV WEYLAND_DB_USER=weyland
ENV WEYLAND_DB_PASSWORD=weyland_dev_password
ENV WEYLAND_QDRANT_URL=http://qdrant.weyland.svc.cluster.local:6333

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
