FROM python:3.11-slim

# Pinned (2026-10-01): an unpinned rebuild pulled Dagster 1.13.25, whose dagster-postgres needs psycopg v3 without
# declaring it — webserver + daemon crash-looped. requirements.txt is frozen to the user-code image's versions.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

ENV DAGSTER_HOME=/opt/dagster/dagster_home
RUN mkdir -p $DAGSTER_HOME
