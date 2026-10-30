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
# 2026-10-30 (B234 Pillar 7): + brotli-python 1.2.1 (CVE-2026-111497, critical) the same way, and conda-rattler-solver +
# py-rattler REMOVED: py-rattler 0.25 bundles the zip crate 8.6.0 (CVE-2026-115905 critical, -115907/8/9), the fix is
# py-rattler 0.28.1, and no conda-rattler-solver release accepts it (0.2.0 needs <0.27). Unused: this conda runs the
# libmamba solver (`conda config --show solver`). --force removes just those two, nothing that depends on them.
RUN conda install -y -c conda-forge --freeze-installed certifi=2026.10.19 ca-certificates=2026.10.19 brotli-python=1.2.1 \
    && conda remove -y --force conda-rattler-solver py-rattler && conda clean -afy
# 2026-10-30: Ubuntu fixes newer than the base tag (libbrotli1 CVE-2026-111497 -> 1.0.9-2ubuntu0.1).
USER root
RUN apt-get update && apt-get upgrade -y --no-install-recommends && rm -rf /var/lib/apt/lists/*
USER ray
COPY requirements-ray-head.txt /tmp/requirements-ray-head.txt
RUN pip install --no-cache-dir -r /tmp/requirements-ray-head.txt
COPY train_genre.py /home/ray/train_genre.py
