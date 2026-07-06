# Genre-classifier trainer image. Built + pushed to the MinIO-backed registry (registry.weyland.lab), then
# pulled + run ephemerally on rogueone (docker run --rm). Small on purpose — it does one job and exits.
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY train_genre.py .

# Args after the image name flow to the script, e.g. `docker run … genre-trainer --source silver --max-depth 12`.
ENTRYPOINT ["python", "train_genre.py"]
