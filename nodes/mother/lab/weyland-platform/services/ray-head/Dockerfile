# Image for the persistent Ray cluster (k8s/ray/) — base Ray (2.56.0, incl. tune + dashboard) plus the
# genre-trainer's runtime deps, so a submitted job finds its imports without a per-job pip install.
# B47: Ray 2.37->2.56 (token-auth capable, clears the DNS-rebinding CVE) + mlflow 2.18->3.14 (RCE CVEs). The
# rogueone worker venv MUST be rebuilt to this same Ray 2.56.0 (env parity) or it won't join the cluster.
#
# The trainer CODE is baked at /home/ray/train_genre.py so the SERVER-SIDE submit paths (Ray Dashboard
# "Submit Job", the Port action) can launch it — `python /home/ray/train_genre.py --tune` — with no client-side
# working_dir upload. Build with the genre-trainer dir as context so train_genre.py is single-sourced:
#   docker build -f services/ray-head/Dockerfile -t registry.weyland.lab/ray-head:vN services/genre-trainer   (next FREE tag)
FROM rayproject/ray:2.56.0-py311

# 2026-10-16: pinned (requirements-ray-head.txt in the genre-trainer context: v7's additions, four raised past advisories).
# 2026-10-22: conda's OWN certifi + CA bundle to 2026.10.19 (GHSA-6q48-6c7w-9gw2). The pip pin below already fixed the
# importable certifi, but conda's record (conda-meta) and its package cache still said 2026.6.17, and the image scanner
# reads those. --freeze-installed moves nothing else; `conda clean` drops the stale cache (~384 MB).
RUN conda install -y -c conda-forge --freeze-installed certifi=2026.10.19 ca-certificates=2026.10.19 && conda clean -afy
COPY requirements-ray-head.txt /tmp/requirements-ray-head.txt
RUN pip install --no-cache-dir -r /tmp/requirements-ray-head.txt
COPY train_genre.py /home/ray/train_genre.py
