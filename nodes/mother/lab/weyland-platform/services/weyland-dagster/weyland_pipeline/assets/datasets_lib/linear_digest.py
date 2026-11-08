"""B237 — the weekly Linear digest: a B194 snapshot -> one Slack message for #linear-updates. Dagster-free; stdlib only.

The nightly B194 job snapshots the whole Linear workspace to MinIO (raw JSON per entity, manifest last). This reads that
snapshot, never the live API, and summarises ONE project (Weyland Lab) over the last 7 days:

  * closed: completed, canceled or marked duplicate inside the window;
  * opened: created inside the window, whatever its state now;
  * the High lane: open, not archived, priority 2, with its hold labels (``parked:*``) shown;
  * stale: open, not archived, untouched (``updatedAt``) for 30+ days: a count plus the oldest 5.

Fail closed: a snapshot older than 26 h, a manifest without ``finished_at``, an unknown project, an empty webhook URL or
anything but HTTP 200 + body ``ok`` from Slack raises ``DigestError``; the job fails and Dagster's failure alerting
reports it. Stale numbers are never sent as this week's. Only absolute imports, so tests load it in isolation.
"""
import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

OPEN_TYPES = {"backlog", "unstarted", "started"}
CLOSED_TYPES = {"completed", "canceled", "duplicate"}
HOLD_PREFIX = "parked:"
SECTION_LIMIT = 3000   # Slack's limit for a section block's text


class DigestError(Exception):
    """Anything that means the digest must NOT be sent (or did not arrive)."""


def _ts(value):
    """Parse Linear's ISO timestamps (``…Z`` or ``+00:00``); None stays None."""
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def check_fresh(manifest, now, max_age_hours=26):
    """Refuse a snapshot whose ``finished_at`` is missing or older than ``max_age_hours``. Returns the age in hours."""
    finished = _ts((manifest or {}).get("finished_at"))
    if finished is None:
        raise DigestError("the snapshot manifest has no finished_at, so its age is unknown; refusing to send")
    age = (now - finished).total_seconds() / 3600
    if age > max_age_hours:
        raise DigestError(f"the newest snapshot is {age:.1f} h old, older than {max_age_hours} h: "
                          "the nightly Linear backup did not run; refusing to send stale numbers")
    return age


def _brief(issue, **extra):
    return {"identifier": issue.get("identifier"), "title": issue.get("title") or "", **extra}


def _project_id(snapshot, project):
    projects = {p.get("name"): p.get("id") for p in snapshot.get("projects") or []}
    if project not in projects:
        raise DigestError(f"project {project!r} is not in the snapshot")
    return projects[project]


def _within(ts, start, end):
    return ts is not None and start <= ts <= end


def _holds(issue, labels):
    return sorted(labels[x] for x in issue.get("labelIds") or [] if labels.get(x, "").startswith(HOLD_PREFIX))


def _classify(issue, state, labels, start, stale_before, now, out):
    """Add one Weyland Lab issue to whichever of the four lists it belongs in."""
    stype, sname = state.get("type"), state.get("name") or "?"
    ended = _ts(issue.get("completedAt")) or _ts(issue.get("canceledAt"))
    created, updated = _ts(issue.get("createdAt")), _ts(issue.get("updatedAt"))
    if stype in CLOSED_TYPES and _within(ended, start, now):
        out["closed"].append((ended, _brief(issue, state=sname)))
    if _within(created, start, now):
        out["opened"].append((created, _brief(issue, state=sname)))
    if stype not in OPEN_TYPES or issue.get("archivedAt"):
        return
    if issue.get("priority") == 2:
        out["high"].append(_brief(issue, holds=_holds(issue, labels), state=sname))
    if updated is not None and updated < stale_before:
        out["stale"].append((updated, _brief(issue, updated=updated.date().isoformat())))


def build_digest(snapshot, now, project="Weyland Lab", days=7, stale_days=30):
    """The digest for ``project`` as a plain dict (lists already sorted)."""
    pid = _project_id(snapshot, project)
    states = {s["id"]: s for s in snapshot.get("workflowStates") or []}
    labels = {lb["id"]: lb.get("name") or "" for lb in snapshot.get("issueLabels") or []}
    start, stale_before = now - timedelta(days=days), now - timedelta(days=stale_days)

    out = {"closed": [], "opened": [], "high": [], "stale": []}
    for i in snapshot.get("issues") or []:
        if ((i.get("project") or {}).get("id")) == pid:
            state = states.get((i.get("state") or {}).get("id")) or {}
            _classify(i, state, labels, start, stale_before, now, out)

    closed, opened, high, stale = out["closed"], out["opened"], out["high"], out["stale"]
    stale.sort(key=lambda t: t[0])
    return {
        "project": project,
        "window_start": start.date().isoformat(),
        "window_end": now.date().isoformat(),
        "closed": [b for _, b in sorted(closed, key=lambda t: t[0])],
        "opened": [b for _, b in sorted(opened, key=lambda t: t[0])],
        "high": sorted(high, key=lambda b: b["identifier"] or ""),
        "stale_count": len(stale),
        "stale_oldest": [b for _, b in stale[:5]],
    }


def _section(title, lines, total, max_items, empty):
    """One section block: a bold heading with the TRUE count, at most ``max_items`` lines, "+N more" for the rest,
    and never more than Slack's 3,000 characters (lines are dropped, and counted into "+N more", to fit)."""
    head = f"*{title} ({total})*"
    if not lines:
        return {"type": "section", "text": {"type": "mrkdwn", "text": f"{head}\n_{empty}_"}}
    shown = list(lines[:max_items])
    while True:
        more = total - len(shown)
        tail = [f"+{more} more"] if more > 0 else []
        text = "\n".join([head, *shown, *tail])
        if len(text) <= SECTION_LIMIT or not shown:
            break
        shown.pop()
    if len(text) > SECTION_LIMIT:   # a single line longer than the limit: cut it, keep the heading and the count
        text = text[: SECTION_LIMIT - 1] + "…"
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


def _line(b):
    return f"• {b['identifier']} {b['title']}"


def format_slack(digest, max_items=10, snapshot=None):
    """The Slack payload: a plain-text fallback plus blocks. Every count is shown even when its list is cut."""
    d = digest
    window = f"{d['window_start']} → {d['window_end']}"
    header = f"Weekly Linear digest: {d['project']}, {window}"
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "Weekly Linear digest"}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text":
            f"{d['project']} · {window}" + (f" · snapshot {snapshot}" if snapshot else "")}]},
        _section("Closed", [f"{_line(b)} ({b['state']})" for b in d["closed"]], len(d["closed"]), max_items,
                 "Nothing closed this week."),
        _section("Opened", [_line(b) for b in d["opened"]], len(d["opened"]), max_items, "Nothing opened this week."),
        _section("High lane", [_line(b) + (f"  [{', '.join(b['holds'])}]" if b["holds"] else "") for b in d["high"]],
                 len(d["high"]), max_items, "The High lane is empty."),
        _section("Stale 30+ days", [f"{_line(b)} (last touched {b['updated']})" for b in d["stale_oldest"]],
                 d["stale_count"], max_items, "Nothing stale."),
    ]
    # The plain-text fallback is what Slack shows in notifications, so it carries the counts and the snapshot too.
    text = (f"{header}: closed {len(d['closed'])}, opened {len(d['opened'])}, High lane {len(d['high'])}, "
            f"stale {d['stale_count']}" + (" (nothing closed)" if not d["closed"] else "")
            + (f" · snapshot {snapshot}" if snapshot else ""))
    return {"text": text, "blocks": blocks}


def _urllib_send(url, body, timeout=20):
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310 - https webhook URL from a Secret
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except urllib.error.URLError as e:
        raise DigestError(f"Slack unreachable: {e.reason}") from None


def post(url, payload, send=_urllib_send):
    """POST the payload to the incoming webhook. Only HTTP 200 with body ``ok`` counts as delivered. The URL is a
    capability, so it never appears in an error."""
    if not url:
        raise DigestError("SLACK_WEBHOOK_LINEAR_UPDATES is not set (Secret weyland/linear-digest-slack, key webhook)")
    status, body = send(url, json.dumps(payload).encode())
    if status != 200 or (body or "").strip() != "ok":
        raise DigestError(f"Slack did not accept the digest: HTTP {status}, body {(body or '')[:80]!r}")
