"""B237 — the weekly Linear digest, posted to Slack #linear-updates (Mondays 05:40 NY, after the 05:20 B194 snapshot).

A thin wrapper: it reads the newest COMPLETE Linear snapshot from MinIO with the B194 helpers (never the live Linear API,
so no new credential), and leaves every decision to the dagster-free ``datasets_lib/linear_digest`` leaf (unit-tested).
The webhook URL comes from Secret ``weyland/linear-digest-slack`` (``optional: true`` in user-code.yaml, so a missing
secret fails only this run). Any failure, including a snapshot older than 26 h or a Slack refusal, fails the run and
dagster-freshness-check alerts; nothing stale or partial is ever sent. Runbook: docs/runbooks/linear-backup.md § Weekly
digest.
"""
import datetime
import json
import os
import urllib.request

import yaml
from dagster import Failure, MetadataValue, Output, asset

from .datasets_lib.linear_digest import (DigestError, build_digest, check_fresh, format_slack, my_work, okr_gaps,
                                         post, pushed_times)
from .linear_backup import _latest_complete_snapshot, _minio, _read_snapshot

PROJECT = "Weyland Lab"
# B119.1: the repo for each My Work project comes from repos.yaml on main (the one source of truth); weyland-lab and
# the My Work repos are public, so neither read needs a credential.
REPOS_YAML_URL = "https://raw.githubusercontent.com/edtbl76/weyland-lab/main/repos.yaml"


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "weyland-linear-digest", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:   # noqa: S310 - fixed https URLs
        return r.read().decode("utf-8")


def _my_work_rows(context, snapshot, now):
    """The B119.1 My Work rows. Commit data that cannot be read becomes "unknown" (no retire flag), never a failure:
    the digest still goes out, and says so."""
    try:
        repos = (yaml.safe_load(_get(REPOS_YAML_URL)) or {}).get("repos") or []
    except Exception as e:   # noqa: BLE001 — unreadable repos.yaml = commit data unknown
        context.log.warning(f"My Work: repos.yaml unreadable ({type(e).__name__}); commit activity unknown")
        repos = None
    projects = {r["project"] for r in my_work(snapshot, now, pushed=None)}
    pushed = pushed_times(repos, projects, lambda url: json.loads(_get(url))) if repos is not None else None
    if pushed is None:
        context.log.warning("My Work: GitHub push times unavailable; no retire check this week")
    return my_work(snapshot, now, pushed=pushed)


@asset(
    group_name="linear_digest",
    description="B237 — weekly digest of the Weyland Lab board (closed / opened in 7 days, the High lane with holds, "
                "30+ day stale) from the newest Linear snapshot, posted to Slack #linear-updates. Refuses a snapshot "
                "older than 26 h. B119.1: also lists the My Work projects with their last activity (Linear + the repo's "
                "last push), flags any idle 6 months while other work arrived ('retire or recommit?'), and names any "
                "active initiative whose OKR section is missing.",
)
def linear_weekly_digest(context) -> Output:
    now = datetime.datetime.now(datetime.timezone.utc)
    client = _minio()
    prefix, manifest = _latest_complete_snapshot(client)
    snapshot_id = prefix.rstrip("/").split("/")[-1]
    try:
        age = check_fresh(manifest, now)
        snapshot = _read_snapshot(client, prefix)
        digest = build_digest(snapshot, now, project=PROJECT)
        rows = _my_work_rows(context, snapshot, now)
        payload = format_slack(digest, snapshot=snapshot_id, my_work=rows, okr_missing=okr_gaps(snapshot))
        post(os.environ.get("SLACK_WEBHOOK_LINEAR_UPDATES", ""), payload)
    except DigestError as e:
        raise Failure(description=f"weekly Linear digest not sent: {e}") from e

    counts = {"closed": len(digest["closed"]), "opened": len(digest["opened"]), "high": len(digest["high"]),
              "stale": digest["stale_count"], "my_work_retire": sum(1 for r in rows if r["retire"])}
    context.log.info(f"posted the weekly Linear digest to #linear-updates: {counts} (snapshot {snapshot_id})")
    return Output(value=counts, metadata={"snapshot": snapshot_id, "snapshot_age_h": round(age, 1),
                                          "window": f"{digest['window_start']} → {digest['window_end']}",
                                          "counts": MetadataValue.json(counts)})
