# B100 P4 — MLflow AI Gateway image.
# The MLflow *tracking* image ships WITHOUT the `[gateway]` extras, so `mlflow gateway` isn't a registered CLI
# command there ("No such command 'gateway'"). This minimal image bakes just those extras (FastAPI/uvicorn/aiohttp/
# tiktoken/slowapi/watchfiles) so we can run the config-driven gateway server. Pinned to 3.14.0 to match the tracking
# server. Config + provider keys are injected at runtime (ConfigMap + env), NOT baked — this image is stateless.
FROM python:3.11-slim

RUN pip install --no-cache-dir 'mlflow[gateway]==3.14.0'

# The gateway is a config-driven server; the ConfigMap-mounted YAML + env come from the Deployment.
EXPOSE 7000
CMD ["mlflow", "gateway", "start", "--config-path", "/config/gateway.yaml", "--host", "0.0.0.0", "--port", "7000"]
