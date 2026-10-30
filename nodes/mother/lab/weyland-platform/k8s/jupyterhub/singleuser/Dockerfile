# B1.8 singleuser image — the datasets-lake toolkit on top of the standard scientific notebook: polars over the 4
# lakeFS silver formats (Parquet/Arrow/Avro/Lance) + DuckDB SQL, all reading the lakeFS S3 gateway via s3fs.
# Built + `ctr import`ed into k3s (single node → no registry); referenced by singleuser.image with pullPolicy Never.
#
# NOTEBOOK DISTRIBUTION (B81): the notebooks under `notebooks/` are baked here at /opt/examples ONLY as a
# cold-start fallback. The LIVE library is git-synced from the public repo into ~/notebooks on every spawn by
# the singleuser postStart hook (see jupyterhub-values.yaml) — git is already in the scipy base, so growing the
# library is a `git push`, NOT an image rebuild. Rebuild this image only to refresh the offline fallback or the
# pinned deps below.
# Pinned by digest (2026-10-17, B220): `:latest` silently jumped ubuntu-24.04 → 26.04 and JupyterHub 5 → 6 between
# rebuilds. This digest = lab-4.6.4 / python-3.13.16 / ubuntu-26.04 (2026-10-12), the one tested. Bump it on purpose.
FROM quay.io/jupyter/scipy-notebook:lab-4.6.4@sha256:8f8a5763d9a01e7f488eff8d9379654788e9cc08286dbcbc6bcda129c1b0edcd
USER root
# 2026-10-18 (B220): `apt-get upgrade` picks up the Ubuntu fixes published after the pinned base digest (curl/libcurl
# 8.18.0-1ubuntu2.8 for CVE-2026-92392), and /usr/bin/pebble is removed: Canonical's service manager ships in the
# ubuntu-26.04 base, nothing here uses it (entrypoint = tini → start.sh → start-notebook.py; /var/lib/pebble/default/layers
# is empty), and its go1.26.7 build carried 3 HIGH Go-stdlib advisories.
RUN apt-get update && apt-get upgrade -y --no-install-recommends \
    && rm -f /usr/bin/pebble && rm -rf /var/lib/pebble /var/lib/apt/lists/*
# 2026-10-22: the conda base's own certifi (2026.7.22), pillow (12.3.0) and pip (26.2.1, which vendors certifi 2026.6.17)
# carried GHSA-6q48-6c7w-9gw2 (certifi, CRITICAL) and pillow's 28 advisories of 2026-10-20/21. They come from the base
# image, so no lockfile named them; requirements-lake.txt now pins all three (pip upgrades conda's copies in place:
# `mamba install --freeze-installed` cannot solve the newer CA bundle without moving the scientific stack). The conda
# package cache, which still holds the old copies, is cleared below.
# 2026-10-16: the additions are pinned (requirements-lake.txt, the versions weyland-jupyter:v1 runs).
COPY requirements-lake.txt /tmp/requirements-lake.txt
RUN pip install --no-cache-dir -r /tmp/requirements-lake.txt \
    && mamba clean -afy \
    && mkdir -p /opt/examples
# 2026-10-20 (B225): nbclassic removed. It bundles `underscore` and `mathjax`, 2 HIGH with no fix in its newest release
# (1.3.3), and nothing uses it: no package requires it, the hub's defaultUrl is /lab, and Notebook 7 serves /tree on its
# own (notebook-shim, not nbclassic). The uninstall must also take its server-extension config, or every spawn would
# try to load a missing extension, so the build fails if that file survives.
RUN pip uninstall -y nbclassic \
    && test ! -e /opt/conda/etc/jupyter/jupyter_server_config.d/nbclassic.json
# 2026-10-30 (B234 Pillar 7): conda-rattler-solver + py-rattler removed. py-rattler 0.26 bundles the zip crate 8.6.0
# (CVE-2026-115905 critical, -115907/8/9 high); the fix is py-rattler 0.28.1 and no conda-rattler-solver release accepts
# it (0.2.0 needs <0.27). Unused: this conda runs the libmamba solver. --force removes just those two.
RUN conda remove -y --force conda-rattler-solver py-rattler && mamba clean -afy \
    && conda config --show solver | grep -q libmamba
COPY notebooks/ /opt/examples/
RUN chmod -R a+rX /opt/examples
USER ${NB_UID}
