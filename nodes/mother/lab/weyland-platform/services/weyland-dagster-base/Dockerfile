FROM python:3.11-slim

RUN pip install --no-cache-dir dagster dagster-graphql dagster-webserver dagster-postgres

ENV DAGSTER_HOME=/opt/dagster/dagster_home
RUN mkdir -p $DAGSTER_HOME
