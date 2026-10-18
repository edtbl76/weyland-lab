# Finance volatility trainer image (B113 Phase 5). Built + pushed to the MinIO-backed registry (registry.weyland.lab), then
# pulled + run ephemerally on rogueone (docker run --rm). Self-contained: given only a mounted kubeconfig it fetches
# its own creds from the k8s Secrets (entrypoint.sh) and reaches MLflow / MinIO / lakeFS over their LAN NodePorts —
# no --network host and no secrets on the command line.
FROM python:3.11-slim

# kubectl → reads the creds from the k8s Secrets (entrypoint.sh); bash → its /dev/tcp NodePort readiness checks.
RUN apt-get update && apt-get install -y --no-install-recommends curl bash ca-certificates \
    && curl -fsSL https://dl.k8s.io/release/v1.30.5/bin/linux/amd64/kubectl -o /usr/local/bin/kubectl \
    && chmod +x /usr/local/bin/kubectl \
    && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
# 2026-10-17 (B220): requirements.txt is now the FULL frozen set (it was 8 bare names, so every build differed). No
# unpinned `pip install --upgrade pip` first, so the base image's pip resolves it the same (check-dockerfile-installs.sh).
RUN pip install --no-cache-dir -r requirements.txt
COPY train_volatility.py entrypoint.sh ./
RUN chmod +x entrypoint.sh

# B47: run as non-root. HOME=/app (owned by appuser) so kubectl config + HF model cache are writable at runtime;
# the ephemeral run mounts a kubeconfig read-only.
RUN useradd -u 10001 -m appuser && chown -R appuser /app
ENV HOME=/app
USER appuser

# Args after the image name flow through entrypoint.sh to the script, e.g. `… genre-trainer --source silver`.
ENTRYPOINT ["./entrypoint.sh"]
