FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
EXPOSE 8080
# B47: run as non-root. Scales deployments via the k8s API (ServiceAccount RBAC, not root); port 8080 is unprivileged.
RUN useradd -u 10001 -m appuser && chown -R appuser /app
USER appuser
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
