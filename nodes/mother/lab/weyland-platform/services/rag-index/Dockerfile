# rag-index consumer image (B-RAG-STREAM). Build on mother + `sudo k3s ctr images import` (imagePullPolicy
# Never), the same local-image path as weyland-flink / dagster. confluent-kafka ships a manylinux wheel with
# librdkafka bundled, so slim + no apt build deps is enough.
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY schema.py consumer.py probe.py heartbeat.py ./
COPY stores ./stores
# B47: run as non-root. The consumer reads /app + streams to Kafka/stores; its one local write is the readiness
# heartbeat file /app/.heartbeat (heartbeat.py). No privileged port.
RUN useradd -u 10001 -m appuser && chown -R appuser /app
USER appuser
CMD ["python", "consumer.py"]
