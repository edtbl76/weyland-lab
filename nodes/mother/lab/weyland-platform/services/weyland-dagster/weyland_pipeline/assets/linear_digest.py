"""B237 — the weekly Linear digest, posted to Slack #linear-updates (Mondays 05:40 NY, after the 05:20 B194 snapshot).

A thin wrapper: it reads the newest COMPLETE Linear snapshot from MinIO with the B194 helpers (never the live Linear API,
so no new credential), and leaves every decision to the dagster-free ``datasets_lib/linear_digest`` leaf (unit-tested).
The webhook URL comes from Secret ``weyland/linear-digest-slack`` (``optional: true`` in user-code.yaml, so a missing
secret fails only this run). Any failure, including a snapshot older than 26 h or a Slack refusal, fails the run and
dagster-freshness-check alerts; nothing stale or partial is ever sent. Runbook: docs/runbooks/linear-backup.md § Weekly
digest.
"""
import datetime
import os

from dagster import Failure, MetadataValue, Output, asset

from .datasets_lib.linear_digest import DigestError, build_digest, check_fresh, format_slack, post
from .linear_backup import _latest_complete_snapshot, _minio, _read_snapshot

PROJECT = "Weyland Lab"


@asset(
    group_name="linear_digest",
    description="B237 — weekly digest of the Weyland Lab board (closed / opened in 7 days, the High lane with holds, "
                "30+ day stale) from the newest Linear snapshot, posted to Slack #linear-updates. Refuses a snapshot "
                "older than 26 h.",
)
def linear_weekly_digest(context) -> Output:
    now = datetime.datetime.now(datetime.timezone.utc)
    client = _minio()
    prefix, manifest = _latest_complete_snapshot(client)
    snapshot_id = prefix.rstrip("/").split("/")[-1]
    try:
        age = check_fresh(manifest, now)
        digest = build_digest(_read_snapshot(client, prefix), now, project=PROJECT)
        payload = format_slack(digest, snapshot=snapshot_id)
        post(os.environ.get("SLACK_WEBHOOK_LINEAR_UPDATES", ""), payload)
    except DigestError as e:
        raise Failure(description=f"weekly Linear digest not sent: {e}") from e

    counts = {"closed": len(digest["closed"]), "opened": len(digest["opened"]), "high": len(digest["high"]),
              "stale": digest["stale_count"]}
    context.log.info(f"posted the weekly Linear digest to #linear-updates: {counts} (snapshot {snapshot_id})")
    return Output(value=counts, metadata={"snapshot": snapshot_id, "snapshot_age_h": round(age, 1),
                                          "window": f"{digest['window_start']} → {digest['window_end']}",
                                          "counts": MetadataValue.json(counts)})
