# Image for the persistent Ray cluster (k8s/ray/) — base Ray (2.56.0, incl. tune + dashboard) plus the
# genre-trainer's runtime deps, so a submitted job finds its imports without a per-job pip install.
# B47: Ray 2.37->2.56 (token-auth capable, clears the DNS-rebinding CVE) + mlflow 2.18->3.14 (RCE CVEs). The
# rogueone worker venv MUST be rebuilt to this same Ray 2.56.0 (env parity) or it won't join the cluster.
#
# The trainer CODE is baked at /home/ray/train_genre.py so the SERVER-SIDE submit paths (Ray Dashboard
# "Submit Job", the Port action) can launch it — `python /home/ray/train_genre.py --tune` — with no client-side
# working_dir upload. Build with the genre-trainer dir as context so train_genre.py is single-sourced:
#   docker build -f services/ray-head/Dockerfile -t registry.weyland.lab/ray-head:v7 services/genre-trainer
FROM rayproject/ray:2.56.0-py311

RUN pip install --no-cache-dir scikit-learn "mlflow==3.14.0" pandas pyarrow minio boto3
COPY train_genre.py /home/ray/train_genre.py
