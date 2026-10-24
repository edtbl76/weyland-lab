# weyland-superset (B227 follow-on, 2026-10-24) — apache/superset 6.1.0 with the lab's database drivers BAKED IN.
# Until then the Helm bootstrap pip-installed psycopg2-binary, trino, authlib and clickhouse-connect UNPINNED into the
# image's venv on every start (PyPI egress at boot, drift on any restart, invisible to every scanner). requirements.txt
# is what that install had added to the running pod, installed --no-deps on top of the same upstream digest, so the
# image's own packages stay exactly as upstream shipped them (see the note in requirements.txt).
#
# Built by hand, like weyland-jupyter (Helm values carry repository + tag separately, which the CI bump PR cannot
# rewrite): runbooks/superset.md § The image. Never move the Superset version here on its own: the chart (0.17.2) and
# the metadata DB migrations move with it.
FROM apachesuperset.docker.scarf.sh/apache/superset:6.1.0@sha256:fb3464528ec7076f91195f0ff7835755aa023e281f1bb78a84782ce7a36b3705

USER root
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --no-deps --target /app/.venv/lib/python3.10/site-packages -r /tmp/requirements.txt \
 && rm /tmp/requirements.txt
USER superset
