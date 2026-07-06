# Image for the persistent Ray cluster (k8s/ray/) — base Ray (2.37.0, incl. tune + dashboard) plus the
# genre-trainer's runtime deps, so a submitted job finds its imports without a per-job pip install.
#
# The trainer CODE is baked at /home/ray/train_genre.py so the SERVER-SIDE submit paths (Ray Dashboard
# "Submit Job", the Port action) can launch it — `python /home/ray/train_genre.py --tune` — with no client-side
# working_dir upload. Build with the genre-trainer dir as context so train_genre.py is single-sourced:
#   docker build -f services/ray-head/Dockerfile -t registry.weyland.lab/ray-head:v1 services/genre-trainer
FROM rayproject/ray:2.37.0-py311

RUN pip install --no-cache-dir scikit-learn "mlflow==2.18.0" pandas pyarrow minio boto3
COPY train_genre.py /home/ray/train_genre.py
