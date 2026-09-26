"""B194 — nightly Linear workspace backup to MinIO (`linear-backup` bucket).

The export logic lives in the dagster-free leaf ``datasets_lib/linear_export.py``; this module owns the three things
that need the runtime: the HTTP transport + the read-only key, the MinIO write, and the dagster asset.

Snapshot layout (one per run): ``s3://linear-backup/snapshots/<UTC ts>/<entity>.json.gz`` for every entity, then
``manifest.json`` (counts, timings, format version) written LAST — a snapshot without a manifest is incomplete by
definition, which is what the restore drill and any reader check first. Snapshots expire after RETENTION_DAYS via a
MinIO lifecycle rule the asset re-applies each run (so the rule is in git, not only in the bucket).

LINEAR_API_KEY_RO comes from the SealedSecret ``linear-backup-secret``; it is read-only (Linear refuses mutations with
FORBIDDEN) and is never logged. Catalogued in docs/dr.md; operated per docs/runbooks/linear-backup.md.
"""
import datetime
import gzip
import io
import json
import os
import time

import httpx
from dagster import Failure, MetadataValue, Output, asset

from .datasets_lib.linear_export import (
    LinearAuthError,
    LinearExportError,
    build_manifest,
    export_workspace,
    snapshot_prefix,
)

LINEAR_URL = "https://api.linear.app/graphql"
BUCKET = os.getenv("LINEAR_BACKUP_BUCKET", "linear-backup")
RETENTION_DAYS = 90
_RETRY_STATUS = {429, 500, 502, 503, 504}


def _send(client, query, variables):
    """One attempt. Returns the parsed body, or None when the status is worth retrying (rate limit, 5xx, network)."""
    try:
        r = client.post(LINEAR_URL, json={"query": query, "variables": variables or {}})
    except httpx.HTTPError:
        return None
    if r.status_code in _RETRY_STATUS:
        return None
    try:
        return r.json()
    except ValueError as e:
        raise LinearExportError(f"HTTP {r.status_code} with a non-JSON body") from e


def _make_post(api_key, retries=4, backoff=2.0):
    """A ``post(query, variables) -> json`` for the leaf. Retries rate limits, 5xx and connection errors; returns the
    parsed body of any other HTTP response unchanged so the leaf classifies it (a 401 carries AUTHENTICATION_ERROR)."""
    client = httpx.Client(timeout=60, headers={"Authorization": api_key, "Content-Type": "application/json",
                                               "User-Agent": "weyland-linear-backup/1.0"})

    def post(query, variables=None):
        for attempt in range(retries):
            body = _send(client, query, variables)
            if body is not None:
                return body
            time.sleep(backoff * (attempt + 1))
        raise LinearExportError(f"Linear API unreachable after {retries} attempts (rate limit, 5xx or network)")

    return post


def _minio():
    from minio import Minio

    return Minio(
        os.environ.get("MINIO_ENDPOINT", "minio.minio.svc.cluster.local:9000"),
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=os.environ.get("MINIO_SECURE", "false").lower() == "true",
    )


def _ensure_bucket(client):
    """Create the bucket if absent and (re)apply the retention rule — idempotent, so git stays the source of truth."""
    from minio.commonconfig import ENABLED, Filter
    from minio.lifecycleconfig import Expiration, LifecycleConfig, Rule

    if not client.bucket_exists(BUCKET):
        client.make_bucket(BUCKET)
    client.set_bucket_lifecycle(BUCKET, LifecycleConfig([
        Rule(ENABLED, rule_filter=Filter(prefix="snapshots/"), rule_id="expire-snapshots",
             expiration=Expiration(days=RETENTION_DAYS)),
    ]))


def _put(client, key, payload):
    """Write one object; ``.gz`` keys are gzip-compressed JSON, everything else plain JSON. Returns bytes written."""
    gz = key.endswith(".gz")
    data = gzip.compress(payload) if gz else payload
    client.put_object(BUCKET, key, io.BytesIO(data), len(data),
                      content_type="application/gzip" if gz else "application/json")
    return len(data)


@asset(
    group_name="linear_backup",
    description="B194 — nightly Linear workspace snapshot (issues + history, comments, projects, initiatives, labels, "
                "templates, views, cycles, …) to s3://linear-backup/snapshots/<ts>/, manifest last, 90-day retention.",
)
def linear_workspace_snapshot(context) -> Output:
    api_key = os.environ.get("LINEAR_API_KEY_RO")
    if not api_key:
        raise Failure(description="LINEAR_API_KEY_RO is not set (expected from the linear-backup-secret SealedSecret)")

    started = datetime.datetime.now(datetime.timezone.utc)
    try:
        snapshot = export_workspace(_make_post(api_key), log=context.log.info)
    except LinearAuthError as e:
        raise Failure(description=f"Linear rejected the read-only key — rotate linear-backup-secret: {e}") from e
    except LinearExportError as e:
        raise Failure(description=f"Linear export incomplete, nothing written: {e}") from e
    finished = datetime.datetime.now(datetime.timezone.utc)

    manifest = build_manifest(snapshot, started, finished)
    prefix = snapshot_prefix(started)
    client = _minio()
    _ensure_bucket(client)
    written = 0
    for entity, nodes in snapshot.items():
        written += _put(client, f"{prefix}{entity}.json.gz", json.dumps(nodes).encode())
    # Manifest LAST: its presence is what marks the snapshot complete.
    written += _put(client, f"{prefix}manifest.json", json.dumps(manifest, indent=2).encode())

    counts = manifest["counts"]
    context.log.info(f"linear backup: wrote {len(snapshot) + 1} objects ({written:,} bytes) to s3://{BUCKET}/{prefix}")
    return Output(
        value=prefix,
        metadata={
            "snapshot": f"s3://{BUCKET}/{prefix}",
            "issues": counts.get("issues", 0),
            "comments": counts.get("comments", 0),
            "issue_history_events": counts.get("issueHistory", 0),
            "bytes_written": written,
            "duration_s": manifest["duration_s"],
            "counts": MetadataValue.json(counts),
        },
    )
