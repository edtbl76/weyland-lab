"""morning_collect.py — what broke overnight, read-only, from the lab's existing signals (B243, 2026-11-24).

Six sources, each a pure parser (tested against fixtures shaped like the real responses observed 2026-11-24) and a
fetcher that does the reading:
  ci          Woodpecker: failed pipelines in the window, one item per FAILED step (killed steps are fallout).
  alerts      Prometheus `ALERTS` that fired in the window: every critical, plus the scheduled-job family.
  dagster     dagster_runs.py --json-since inside the dagster-user-code pod (runs the morning runner itself
              re-executed are marked agent-caused).
  glitchtip   unresolved GlitchTip issues seen in the window, through its Django shell (read-only ORM query).
  incidents   U14's machine-filed incidents in Linear project "Weyland Auto-Filed" (LINEAR_API_KEY_RO).
  dependabot  new high or critical Dependabot alerts in the active repos of repos.yaml (gh api).
A source that cannot be read is reported as NOT CHECKED, never as "nothing broke". The same cause is one item.
Evidence is scrubbed of secret-shaped text before it can reach a report. Tests: scripts/tests/test_morning_collect.py.
Runbook: docs/runbooks/morning-remediation.md.
"""
import base64
import dataclasses
import datetime
import json
import os
import pathlib
import re
import subprocess
import urllib.parse
import urllib.request

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
PROMETHEUS = os.environ.get("PROMETHEUS_URL", "http://mother:30909")   # prometheus-lan NodePort, read-only (docs/api.md)
WOODPECKER_REPO = "edtbl76/weyland-lab"
LOG_TAIL = 15
ALERT_FAMILY = {"KubeJobFailed", "ScheduledJobFailed", "ScheduledJobStale", "ScheduledBackupFailed"}
ALERT_NOISE = {"InfoInhibitor", "Watchdog"}
CRON_KEY = "cronjob:"   # an item whose cause is a CronJob
_SECRET = re.compile(r"(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|glpat-[A-Za-z0-9_-]{16,}"
                     r"|sk-[A-Za-z0-9_-]{16,}|xox[abpr]-[A-Za-z0-9-]{8,}|lin_api_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16})")
_BEARER = re.compile(r"(?i)(bearer\s+)\S+")
_ASSIGNED = re.compile(r"(?i)\b(password|passwd|secret|token|api[_-]?key)\s*[=:]\s*\S+")


class SourceUnavailable(Exception):
    """The source could not be read; the report must say so."""


@dataclasses.dataclass
class Failure:
    source: str
    key: str            # one item per cause: the same key from anywhere is merged
    title: str
    evidence: str = ""
    link: str = ""
    agent_caused: bool = False
    extra: dict = dataclasses.field(default_factory=dict)


def scrub(text: str) -> str:
    text = _SECRET.sub("[redacted]", text or "")
    text = _BEARER.sub(r"\1[redacted]", text)
    return _ASSIGNED.sub(lambda m: f"{m.group(1)}=[redacted]", text)


def iso_to_epoch(value: str) -> float:
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


# --- parsers (pure) -------------------------------------------------------------------------------------------------
def _log_text(entries: list) -> str:
    lines = [base64.b64decode(e["data"]).decode(errors="replace") for e in entries or [] if e.get("data")]
    return scrub("\n".join(lines[-LOG_TAIL:]))


def _failed(p: dict, since: float, last_green: float = 0) -> bool:
    """Failed in the window, and not superseded by a later green pipeline (that one proves it is fixed)."""
    created = p.get("created", 0)
    return created >= since and created > last_green and p.get("status") in ("failure", "error")


def failed_steps(pipeline: dict):
    """(workflow, step) for each FAILED step; killed steps are fallout from another failure, not causes."""
    for wf in pipeline.get("workflows") or []:
        for step in wf.get("children") or []:
            if step.get("state") == "failure":
                yield wf, step


def parse_woodpecker(pipelines: list, logs: dict, since: float, last_green: float = 0) -> list:
    out = []
    for p in pipelines:
        if not _failed(p, since, last_green):
            continue
        for wf, step in failed_steps(p):
            out.append(Failure("ci", f"ci:{wf['name']}/{step['name']}",
                               f"CI #{p['number']} ({p['event']}): {wf['name']} / {step['name']} failed "
                               f"(exit {step.get('exit_code')})", _log_text(logs.get(step["id"])),
                               p.get("forge_url", ""),
                               extra={"pipeline": p["number"], "event": p["event"], "step_id": step["id"],
                                      "nightly": p["event"] == "cron"}))
    return out


_RUN_SUFFIX = re.compile(r"-\d{6,}$")   # a CronJob's Job is <cronjob>-<scheduled minute>


def parse_alerts(series: list) -> list:
    out = []
    for s in series:
        m = s.get("metric") or {}
        name = m.get("alertname", "")
        if name in ALERT_NOISE or not (m.get("severity") == "critical" or name in ALERT_FAMILY):
            continue
        if name in ALERT_FAMILY and m.get("namespace") and (m.get("cronjob") or m.get("job_name")):
            cron = m.get("cronjob") or _RUN_SUFFIX.sub("", m["job_name"])
            extra = {"namespace": m["namespace"], "cronjob": cron}
            if m.get("job_name"):
                extra["job_name"] = m["job_name"]
            out.append(Failure("alerts", f"{CRON_KEY}{m['namespace']}/{cron}",
                               f"CronJob {m['namespace']}/{cron} failed or went stale", f"{name}: {m.get('job_name', cron)}",
                               extra=extra))
            continue
        subject = m.get("instance") or m.get("namespace") or m.get("job") or "-"
        out.append(Failure("alerts", f"alert:{name}:{subject}", f"{name} ({m.get('severity')}) on {subject}",
                           scrub(json.dumps(m, sort_keys=True)), extra={"labels": m}))
    return out


def parse_dagster(rows: list) -> list:
    return [Failure("dagster", f"dagster:{r['jobName']}", f"Dagster run {r['runId']} of {r['jobName']} failed",
                    scrub("\n".join(r.get("failures") or [])), agent_caused=bool(r.get("started_by_agent")),
                    extra={"run_id": r["runId"], "run_ids": [r["runId"]], "job": r["jobName"],
                           "job_defined": r.get("job_defined", True)}) for r in rows]


def parse_glitchtip(rows: list, since: float) -> list:
    out = []
    for r in rows:
        if r.get("status") == "resolved" or r.get("last_seen", 0) < since:
            continue
        kind = "new" if r.get("first_seen", 0) >= since else "recurring"
        out.append(Failure("glitchtip", f"glitchtip:{r['project']}/{r['short_id']}",
                           f"GlitchTip {kind} {r['level']} in {r['project']}: {r['title']}",
                           scrub(f"{r.get('culprit', '')} — {r.get('count')} event(s)"),
                           extra={"issue_id": r["id"], "new": kind == "new"}))
    return out


def parse_linear(issues: list, since: float) -> list:
    closed = ("canceled", "completed")   # a closed incident needs nothing (2026-11-25: EMA-360 was commented after cancel)
    return [Failure("incidents", f"incident:{i['identifier']}", f"Incident {i['identifier']}: {i['title']}",
                    f"state {(i.get('state') or {}).get('name')}", i.get("url", ""),
                    extra={"identifier": i["identifier"]})
            for i in issues if iso_to_epoch(i["createdAt"]) >= since and (i.get("state") or {}).get("type") not in closed]


def parse_dependabot(repo: str, alerts: list, since: float) -> list:
    out = []
    for a in alerts:
        sev = (a.get("security_advisory") or {}).get("severity")
        if sev not in ("high", "critical") or iso_to_epoch(a["created_at"]) < since:
            continue
        pkg = ((a.get("dependency") or {}).get("package") or {}).get("name", "?")
        out.append(Failure("dependabot", f"dependabot:{repo}/{pkg}",
                           f"Dependabot {sev} in {repo}: {pkg} ({a['security_advisory'].get('summary', '')})",
                           link=a.get("html_url", ""), extra={"repo": repo, "number": a.get("number")}))
    return out


# --- the collection -----------------------------------------------------------------------------------------------
def collect(since: float, fetchers: dict) -> tuple:
    """(failures merged by cause, {source: "checked" | "checked (note)" | "NOT CHECKED: reason"})."""
    merged, status = {}, {}
    for name, fetch in fetchers.items():
        try:
            got = fetch(since)
        except SourceUnavailable as exc:
            status[name] = f"NOT CHECKED: {exc}"
            continue
        except Exception as exc:   # any failure to read is "not checked", never "nothing broke"
            status[name] = f"NOT CHECKED: {type(exc).__name__}: {str(exc)[:200]}"
            continue
        items, note = got if isinstance(got, tuple) else (got, "")
        status[name] = f"checked ({note})" if note else "checked"
        for f in items:
            _merge(merged, f)
    folded = _fold_run_reports(list(merged.values()))
    # A failed run of a job the code no longer defines is nothing left to fix (2026-11-25). Dropped AFTER the fold, so
    # GlitchTip's reports about that run leave with it instead of being reported on their own.
    return [f for f in folded if f.extra.get("job_defined", True)], status


def _merge(merged: dict, f: Failure) -> None:
    """The same cause is one item: later evidence is appended, and a Dagster item keeps every failed run's id."""
    first = merged.setdefault(f.key, f)
    if first is f:
        return
    first.evidence = (first.evidence + "\n" + f.evidence).strip()
    if "run_ids" in f.extra:
        first.extra["run_ids"] = first.extra.get("run_ids", []) + f.extra["run_ids"]


def _fold_run_reports(items: list) -> list:
    """A GlitchTip issue that names a failed Dagster run's id is Dagster reporting that run (STEP_FAILURE /
    RUN_FAILURE): the same cause as the Dagster item, so it joins that item instead of being triaged again."""
    runs = {rid: f for f in items if f.source == "dagster"
            for rid in {*(f.extra.get("run_ids") or []), f.extra.get("run_id")} if rid}
    kept = []
    for f in items:
        owner = next((d for rid, d in runs.items() if f.source == "glitchtip" and rid in f.title), None)
        if owner is None:
            kept.append(f)
        else:
            owner.evidence = (owner.evidence + f"\nalso reported to GlitchTip as {f.key.split(':', 1)[1]}").strip()
    return kept


# --- fetchers (I/O) -----------------------------------------------------------------------------------------------
def _http_json(url: str, headers: dict | None = None, data: bytes | None = None, timeout: int = 30):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except Exception as exc:
        raise SourceUnavailable(f"{urllib.parse.urlsplit(url).netloc}: {type(exc).__name__}: {exc}"[:200]) from exc


def _run(argv: list, stdin: str | None = None, timeout: int = 120) -> str:
    done = subprocess.run(argv, input=stdin, capture_output=True, text=True, timeout=timeout)
    if done.returncode != 0:
        raise SourceUnavailable(f"{argv[0]} exit {done.returncode}: {(done.stderr or done.stdout).strip()[-200:]}")
    return done.stdout


def fetch_ci(since: float):
    server, token = os.environ.get("WOODPECKER_SERVER"), os.environ.get("WOODPECKER_TOKEN")
    if not server or not token:
        raise SourceUnavailable("WOODPECKER_SERVER / WOODPECKER_TOKEN not set")
    h = {"Authorization": f"Bearer {token}"}
    repo = _http_json(f"{server}/api/repos/lookup/{WOODPECKER_REPO}", h)["id"]
    listed = _http_json(f"{server}/api/repos/{repo}/pipelines?perPage=50", h)
    last_green = max((p.get("created", 0) for p in listed if p.get("status") == "success"), default=0)
    pipelines, logs = [], {}
    for p in (p for p in listed if _failed(p, since, last_green)):
        detail = _http_json(f"{server}/api/repos/{repo}/pipelines/{p['number']}", h)
        pipelines.append(detail)
        for _wf, step in failed_steps(detail):
            logs[step["id"]] = _http_json(f"{server}/api/repos/{repo}/logs/{p['number']}/{step['id']}", h)
    return parse_woodpecker(pipelines, logs, since, last_green)


def _owner_and_failure(job: dict) -> tuple:
    owner = next((r["name"] for r in (job.get("metadata") or {}).get("ownerReferences") or []
                  if r.get("kind") == "CronJob"), None)
    failed = next((c.get("lastTransitionTime") for c in (job.get("status") or {}).get("conditions") or []
                   if c.get("type") == "Failed"), None)
    return owner, failed


def _settle_one(f: Failure, jobs: dict, crons: dict, since) -> Failure | None:
    """The item, re-keyed to its owning CronJob, or None when it is no longer broken."""
    job = jobs.get(f.extra.get("job_name"))
    owner, failed_at = _owner_and_failure(job) if job else (None, None)
    cron = owner or f.extra["cronjob"]
    if cron not in crons:
        return None                                    # the CronJob no longer exists: nothing left to fix
    last_ok = crons[cron]
    failure = iso_to_epoch(failed_at) if failed_at else since
    if last_ok and failure is not None and iso_to_epoch(last_ok) > failure:
        return None                                    # a later run succeeded: superseded, like a CI failure
    ns = f.extra["namespace"]
    f.key, f.title = f"{CRON_KEY}{ns}/{cron}", f"CronJob {ns}/{cron} failed or went stale"
    f.extra["cronjob"] = cron
    return f


def settle_cronjobs(items: list, jobs_by_ns: dict, crons_by_ns: dict, since: float | None = None) -> list:
    """First unattended run, 2026-11-25: name each failed Job's CronJob from the Job's ownerReference (a hand-started
    `<cj>-manual-<ts>` Job is still `<cj>`), and drop an item that is no longer broken: its CronJob is gone, or the
    CronJob's last success is newer than the failure (failed Jobs keep their alerts firing for their 72 h TTL)."""
    kept = []
    for f in items:
        if not f.key.startswith(CRON_KEY):
            kept.append(f)
            continue
        ns = f.extra["namespace"]
        jobs = {j["metadata"]["name"]: j for j in jobs_by_ns.get(ns) or []}
        crons = {c["metadata"]["name"]: (c.get("status") or {}).get("lastSuccessfulTime") for c in crons_by_ns.get(ns) or []}
        settled = _settle_one(f, jobs, crons, since)
        if settled is not None:
            kept.append(settled)
    return kept


def _cluster_list(kind: str, ns: str) -> list:
    return json.loads(_run(["kubectl", "-n", ns, "get", kind, "-o", "json"])).get("items") or []


def attach_job_logs(items: list, list_jobs, read_log) -> None:
    """For each CronJob item, the newest failed Job's log tail as evidence (the WHY the alert cannot carry). A log that
    is gone (the pod was reaped) is said, never treated as a failure of the source."""
    listings = {}
    for f in (i for i in items if i.key.startswith(CRON_KEY)):
        ns, cron = f.extra["namespace"], f.extra["cronjob"]
        if ns not in listings:
            listings[ns] = list_jobs(ns)
        failed = sorted(ln.split()[0] for ln in listings[ns].splitlines()
                        if ln.split() and _RUN_SUFFIX.sub("", ln.split()[0]) == cron and "Failed" in ln.split()[1:])
        if not failed:
            continue
        job = failed[-1]
        try:
            tail = read_log(ns, job)
        except Exception as exc:   # evidence is best effort: the item is still reported
            tail = f"log unavailable ({type(exc).__name__}: {str(exc)[:120]})"
        f.evidence = (f.evidence + f"\nlog of {job} (last lines):\n" + scrub("\n".join(tail.splitlines()[-LOG_TAIL:]))).strip()


def _list_jobs(ns: str) -> str:
    return _run(["kubectl", "-n", ns, "get", "jobs", "--no-headers", "-o",
                 "custom-columns=NAME:.metadata.name,FAILED:.status.conditions[?(@.type==\"Failed\")].type"])


def _read_job_log(ns: str, job: str) -> str:
    return _run(["kubectl", "-n", ns, "logs", f"job/{job}", "--tail", str(LOG_TAIL * 2)])


def fetch_alerts(since: float):
    window = max(60, int(datetime.datetime.now(datetime.timezone.utc).timestamp() - since))
    q = urllib.parse.urlencode({"query": f'max_over_time(ALERTS{{alertstate="firing"}}[{window}s])'})
    data = _http_json(f"{PROMETHEUS}/api/v1/query?{q}")
    if data.get("status") != "success":
        raise SourceUnavailable(f"Prometheus answered {data.get('status')}")
    items = parse_alerts(data["data"]["result"])
    namespaces = sorted({f.extra["namespace"] for f in items if f.key.startswith(CRON_KEY)})
    items = settle_cronjobs(items, {ns: _cluster_list("jobs", ns) for ns in namespaces},
                            {ns: _cluster_list("cronjobs", ns) for ns in namespaces}, since)
    attach_job_logs(items, _list_jobs, _read_job_log)
    return items


def fetch_dagster(since: float):
    out = _run(["kubectl", "exec", "-i", "-n", "weyland", "deploy/dagster-user-code", "--", "python3", "-",
                "--json-since", str(int(since))], stdin=(ROOT / "scripts" / "lib" / "dagster_runs.py").read_text())
    return parse_dagster(json.loads(out.strip().splitlines()[-1]))


_GLITCHTIP_QUERY = """
import json, datetime
from django.apps import apps
X = apps.get_model("issue_events", "IssueIndex")   # last_seen, count, status, level live here (observed 2026-11-24)
since = datetime.datetime.fromtimestamp(SINCE, tz=datetime.timezone.utc)
disp = lambda o, f: str(getattr(o, f"get_{f}_display")()) if hasattr(o, f"get_{f}_display") else str(getattr(o, f))
rows = []
for x in X.objects.filter(last_seen__gte=since).select_related("issue__project")[:200]:
    i = x.issue
    rows.append({"id": i.id, "short_id": f"{i.project.slug.upper()}-{i.short_id}", "title": (i.title or "")[:200],
                 "culprit": (i.culprit or "")[:200], "level": disp(x, "level"), "status": disp(x, "status").lower(),
                 "first_seen": i.first_seen.timestamp(), "last_seen": x.last_seen.timestamp(), "count": x.count,
                 "project": i.project.slug})
print("MORNING-JSON " + json.dumps(rows))
"""


def fetch_glitchtip(since: float):
    out = _run(["kubectl", "exec", "-i", "-n", "weyland", "deploy/glitchtip-web", "--", "./manage.py", "shell"],
               stdin=_GLITCHTIP_QUERY.replace("SINCE", str(int(since))), timeout=180)
    line = next((ln for ln in out.splitlines() if ln.startswith("MORNING-JSON ")), None)
    if line is None:
        raise SourceUnavailable("GlitchTip's shell printed no result")
    return parse_glitchtip(json.loads(line[len("MORNING-JSON "):]), since)


def fetch_incidents(since: float):
    key = os.environ.get("LINEAR_API_KEY_RO")
    if not key:
        raise SourceUnavailable("LINEAR_API_KEY_RO not set")
    iso = datetime.datetime.fromtimestamp(since, tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    query = ('query($since: DateTimeOrDuration!){issues(first: 50, filter: {project: {name: {eq: "Weyland Auto-Filed"}}, '
             'createdAt: {gte: $since}}){nodes{identifier title url createdAt state{name type}}}}')
    data = _http_json("https://api.linear.app/graphql", {"Content-Type": "application/json", "Authorization": key},
                      json.dumps({"query": query, "variables": {"since": iso}}).encode())
    if data.get("errors"):
        raise SourceUnavailable(f"Linear: {data['errors'][0].get('message')}")
    return parse_linear(data["data"]["issues"]["nodes"], since)


def active_repos() -> list:
    doc = yaml.safe_load((ROOT / "repos.yaml").read_text())
    return [r["name"] for r in doc.get("repos") or [] if r.get("status") == "active"]


def fetch_dependabot(since: float):
    out, failed = [], []
    repos = active_repos()
    for repo in repos:
        try:
            alerts = json.loads(_run(["gh", "api", f"repos/edtbl76/{repo}/dependabot/alerts?state=open&per_page=100"]))
        except (SourceUnavailable, ValueError):
            failed.append(repo)
            continue
        out += parse_dependabot(repo, alerts, since)
    if repos and len(failed) == len(repos):
        raise SourceUnavailable("no repository's Dependabot alerts could be read")
    return out, (f"{len(failed)} repo(s) unreadable: {', '.join(failed)}" if failed else "")


FETCHERS = {"ci": fetch_ci, "alerts": fetch_alerts, "dagster": fetch_dagster, "glitchtip": fetch_glitchtip,
            "incidents": fetch_incidents, "dependabot": fetch_dependabot}
