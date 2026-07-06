# Genre-classifier trainer image. Built + pushed to the MinIO-backed registry (registry.weyland.lab), then
# pulled + run ephemerally on rogueone (docker run --rm). Self-contained: given only a mounted kubeconfig it
# fetches its own creds (ensure_creds) AND opens its own port-forwards to the cluster (entrypoint.sh) — so the
# run needs no host port-forwards, no --network host, and no secrets on the command line.
FROM python:3.11-slim

# kubectl → the in-container port-forwards (entrypoint.sh); bash → its /dev/tcp readiness checks.
RUN apt-get update && apt-get install -y --no-install-recommends curl bash ca-certificates \
    && curl -fsSL https://dl.k8s.io/release/v1.30.5/bin/linux/amd64/kubectl -o /usr/local/bin/kubectl \
    && chmod +x /usr/local/bin/kubectl \
    && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY train_genre.py entrypoint.sh ./
RUN chmod +x entrypoint.sh

# Args after the image name flow through entrypoint.sh to the script, e.g. `… genre-trainer --source silver`.
ENTRYPOINT ["./entrypoint.sh"]
