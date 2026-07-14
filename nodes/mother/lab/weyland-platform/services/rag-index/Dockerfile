# rag-index consumer image (B-RAG-STREAM). Build on mother + `sudo k3s ctr images import` (imagePullPolicy
# Never), the same local-image path as weyland-flink / dagster. confluent-kafka ships a manylinux wheel with
# librdkafka bundled, so slim + no apt build deps is enough.
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY schema.py consumer.py probe.py ./
COPY stores ./stores
CMD ["python", "consumer.py"]
