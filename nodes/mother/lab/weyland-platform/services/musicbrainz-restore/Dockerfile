# mbslave runner — the reusable MusicBrainz restore image. Same image serves the ad-hoc smoke-test Job today
# and the Dagster-triggered restore Job later; only the env (dump source) changes, never the image.
#
# mbslave (acoustid/mbslave) is a lightweight pure-Python MusicBrainz mirror tool — no MB Perl server stack.
# `mbslave init --create-user --create-database` creates the DB + user + schema and imports the latest dump.
# All config is via MBSLAVE_DB_* env vars (set by the Job from the instance Secret) — no mounted config file,
# which is what lets one image work in both Job contexts.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        postgresql-client bzip2 ca-certificates git curl \
    && rm -rf /var/lib/apt/lists/*

# Pin to a ref once the smoke test proves a working commit — @main for the first pass.
RUN pip install --no-cache-dir "git+https://github.com/acoustid/mbslave.git@main"

WORKDIR /tmp/mbslave        # dump download + TSV extraction land here (mount an emptyDir/PVC at this path)
ENTRYPOINT ["mbslave"]
CMD ["init", "--create-user", "--create-database"]
