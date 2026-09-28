"""DataHub ingestion watchdog (B197) — alert on DataHub managed-ingestion sources that fail or stop.

WHY THIS EXISTS: two sources (`dbt - Weyland`, `MLFlow - Weyland`) failed every day for 10+ days in September 2026 and
nothing alerted; dbt docs, tests and column lineage silently stopped reaching the catalog while the DataHub coverage
guard stayed green (the Iceberg source catalogs the same tables). Found only while closing B194.

WHAT IT DOES: reads every ingestion source and its recent runs from DataHub's GraphQL API and, per source, posts to
Alertmanager (→ Telegram):
  DataHubIngestionFailed    the latest run FAILURE / ABORTED
  DataHubIngestionStale     no SUCCESS within the budget (2x the schedule interval, 1h floor) — a run orphaned in
                            RUNNING, or a CANCELLED one, is not a success, so this is what catches it; also any
                            unscheduled source that is not an accepted on-demand one
  DataHubIngestionNeverRan  a scheduled source with no run at all (the B196 never-ran class)

WHY GRAPHQL AND NOT `datahub_ingestion_runs` (TimescaleDB): that table is a copy made by the nightly
`weyland_timeseries_job` (00:20). Alerting from it would lag a failure by up to a day and depend on a second job being
healthy — the watchdog would inherit the failure mode it exists to catch. GMS is the authority.

EXIT CODES: 0 checked (alerts fired as needed) · 1 an alert could not be delivered (a watchdog that did not watch —
the failed Job then pages through ScheduledJobFailed) · 2 could not read (GMS unreachable, GraphQL errors, empty or
short source list, an unmodelled schedule) — never a pass.
"""
import argparse
import json
import os
import sys
import time
import urllib.request

SOURCE_LABEL = "datahub-ingestion-watchdog"
FAILED = {"FAILURE", "ABORTED"}
PAGE = 50
RUNS = 20  # runs read per source: enough that a burst of manual retries cannot hide an older success
# On-demand sources, accepted by URN with the reason. Anything else without a schedule alerts.
ACCEPTED_ON_DEMAND = {
    "urn:li:dataHubIngestionSource:cli-151c2b7711eb626e440af8c75a9082e9":
        "[CLI] dbt — created by a one-off `datahub ingest` CLI run (2026-07-12); scheduled dbt ingestion is 'dbt - Weyland'",
}
QUERY = ("query($start:Int!,$count:Int!){ listIngestionSources(input:{start:$start,count:$count}) { total "
         "ingestionSources { urn name type schedule { interval timezone } "
         f"executions(start:0,count:{RUNS}) "
         "{ executionRequests { id input { requestedAt } result { status startTimeMs } } } } } }")


class CannotRead(Exception):
    """A source of truth could not be read — exit 2, never a clean report."""


# --- schedule → budget ---------------------------------------------------------------------------------------------

def period_seconds(cron):
    """Only the shapes DataHub sources use here: daily `M H * * *`, weekly `M H * * D`, `*/N * * * *`. Anything else
    is refused, because a guessed period is a wrong budget."""
    f = str(cron or "").split()
    if len(f) != 5:
        raise CannotRead(f"cannot parse schedule {cron!r}")
    m, h, dom, mon, dow = f
    if dom != "*" or mon != "*":
        raise CannotRead(f"unmodelled schedule {cron!r} (day-of-month/month)")
    if m.startswith("*/") and h == "*" and dow == "*" and m[2:].isdigit():
        return int(m[2:]) * 60
    if m.isdigit() and h.isdigit():
        if dow == "*":
            return 86400
        if dow.isdigit():
            return 604800
    raise CannotRead(f"unmodelled schedule {cron!r}")


def budget_seconds(period):
    return max(2 * period, 3600)


# --- verdicts ------------------------------------------------------------------------------------------------------

def _runs(source):
    rows = ((source.get("executions") or {}).get("executionRequests")) or []
    out = []
    for r in rows:
        res = r.get("result") or {}
        t = res.get("startTimeMs") or (r.get("input") or {}).get("requestedAt") or 0
        out.append((t / 1000.0, res.get("status") or "PENDING"))
    return sorted(out, reverse=True)


def _verdict(source, now, factor):
    name, cron = source["name"], (source.get("schedule") or {}).get("interval")
    runs = _runs(source)
    if not cron:
        if source["urn"] in ACCEPTED_ON_DEMAND:
            return None
        return ("DataHubIngestionStale", name, "has no schedule and is not an accepted on-demand source")
    if not runs:
        return ("DataHubIngestionNeverRan", name, f"scheduled {cron} but has never run")
    if runs[0][1] in FAILED:
        return ("DataHubIngestionFailed", name, f"latest run {runs[0][1]}")
    budget = budget_seconds(period_seconds(cron)) * factor
    last_ok = next((t for t, s in runs if s == "SUCCESS"), None)
    if last_ok is None or now - last_ok > budget:
        age = f"none in the last {len(runs)} runs" if last_ok is None else f"{int(now - last_ok)}s ago"
        return ("DataHubIngestionStale", name, f"no SUCCESS within {int(budget)}s (last success: {age})")
    return None


def verdicts(sources, now, factor=1.0, only=None):
    out = []
    for s in sources:
        if only and s["name"] != only:
            continue
        v = _verdict(s, now, factor)
        if v:
            out.append(v)
    return out


# --- GMS -----------------------------------------------------------------------------------------------------------

def list_sources(gql):
    got, start, total = [], 0, None
    while total is None or start < total:
        resp = gql(QUERY, {"start": start, "count": PAGE})
        if not isinstance(resp, dict) or resp.get("errors") or not resp.get("data"):
            raise CannotRead(f"GraphQL error: {(resp or {}).get('errors') if isinstance(resp, dict) else resp}")
        page = resp["data"]["listIngestionSources"]
        total, rows = page["total"], page["ingestionSources"] or []
        if not rows:
            break
        got += rows
        start += len(rows)
    if not got:
        raise CannotRead("GMS returned no ingestion sources — refusing to report a clean catalog")
    if len(got) < (total or 0):
        raise CannotRead(f"GMS said {total} sources but returned {len(got)} — refusing a partial check")
    return got


def _gms(url, token):
    def gql(query, variables):
        req = urllib.request.Request(f"{url.rstrip('/')}/api/graphql",
                                     data=json.dumps({"query": query, "variables": variables}).encode(),
                                     headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:  # nosec B310 — URL comes from --gms / DATAHUB_GMS_URL
                return json.load(resp)
        except (OSError, ValueError) as exc:
            raise CannotRead(f"GMS unreachable at {url}: {exc}") from exc
    return gql


# --- alerts --------------------------------------------------------------------------------------------------------

def alert_payload(alertname, source, reason):
    return [{"labels": {"alertname": alertname, "severity": "warning", "namespace": "data-mesh",
                        "ingestion_source": source, "source": SOURCE_LABEL},
             "annotations": {"summary": f"DataHub ingestion '{source}': {reason}",
                             "description": f"{reason}. Inspect the source's run history at "
                                            "https://datahub.weyland.lab/ingestion (runbook: docs/runbooks/datahub.md)."}}]


def _post_alert(url, body):
    req = urllib.request.Request(f"{url.rstrip('/')}/api/v2/alerts", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30):  # nosec B310 — URL comes from --alertmanager / ALERTMANAGER_URL
        pass


# --- main ----------------------------------------------------------------------------------------------------------

def _args(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--gms", default=os.environ.get("DATAHUB_GMS_URL"))
    ap.add_argument("--token", default=os.environ.get("DATAHUB_GMS_TOKEN"))
    ap.add_argument("--alertmanager", default=os.environ.get("ALERTMANAGER_URL"))
    ap.add_argument("--factor", type=float, default=float(os.environ.get("BUDGET_FACTOR", "1")),
                    help="multiply every budget (a drill uses a tiny factor)")
    ap.add_argument("--only", default=os.environ.get("ONLY_SOURCE"), help="check one source by name (drills)")
    return ap.parse_args(argv)


def main(argv=None):
    a = _args(argv)
    missing = [n for n, v in (("DATAHUB_GMS_URL/--gms", a.gms), ("DATAHUB_GMS_TOKEN/--token", a.token),
                              ("ALERTMANAGER_URL/--alertmanager", a.alertmanager)) if not v]
    if missing:
        print(f"❌ cannot check DataHub ingestion: missing {', '.join(missing)}", file=sys.stderr)
        return 2
    try:
        sources = list_sources(_gms(a.gms, a.token))
        found = verdicts(sources, time.time(), a.factor, a.only)
    except CannotRead as exc:
        print(f"❌ cannot check DataHub ingestion: {exc}", file=sys.stderr)
        return 2
    undelivered = 0
    for alertname, source, reason in found:
        print(f"ALERT {alertname} source={source!r} :: {reason}")
        try:
            _post_alert(a.alertmanager, alert_payload(alertname, source, reason))
        except OSError as exc:
            print(f"  !! Alertmanager POST failed: {exc}", file=sys.stderr)
            undelivered += 1
    print(f"checked {len(sources)} source(s): {len(found)} alert(s) fired")
    return 1 if undelivered else 0


if __name__ == "__main__":
    sys.exit(main())
