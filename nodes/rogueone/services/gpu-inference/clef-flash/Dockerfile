# Clef-flash on-demand decision server (B174) — see server.py. Built and run by scripts/clef-flash.sh on rogueone's
# native Docker engine (the nvidia runtime; Docker Desktop has no GPU). Weights download to the shared hf-cache volume
# on first start (~19 GB), pinned to a full commit.
FROM pytorch/pytorch:2.14.1-cuda13.0-cudnn9-runtime
COPY requirements.txt /tmp/requirements.txt
# The base image marks its Python EXTERNALLY-MANAGED (PEP 668); in a single-purpose container there is no OS Python to
# protect, and installing beside the image's own torch is the point.
RUN pip install --no-cache-dir --break-system-packages -r /tmp/requirements.txt
WORKDIR /app
COPY server.py /app/
EXPOSE 8080
CMD ["python", "server.py"]
