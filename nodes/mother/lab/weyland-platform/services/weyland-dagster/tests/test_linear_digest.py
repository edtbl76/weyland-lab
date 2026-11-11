"""Tests for the dagster-free ``linear_digest`` leaf (B237 — the weekly Linear digest to Slack #linear-updates).

It reads a B194 snapshot (raw Linear JSON, one list per entity) and summarises project Weyland Lab over the last 7 days:
what closed, what opened, the open High lane with its hold labels, and open issues untouched for 30+ days. It refuses a
snapshot older than 26 h (stale numbers must never pose as this week's), formats one Slack message inside Slack's block
limits without ever dropping a count, and treats anything but HTTP 200 + body ``ok`` from the webhook as a failure.

Node shapes are copied from the real snapshot of 2026-11-07T10:20Z: issues carry ``project``/``state`` as ``{"id"}``
refs, ``labelIds``, ``priority``, ``createdAt``/``updatedAt``/``completedAt``/``canceledAt``/``archivedAt``; labels are
flat names (``parked:held``, ``parked:deferred``); state types are backlog/unstarted/started/completed/canceled/duplicate.
"""
from datetime import datetime, timedelta, timezone

import pytest

NOW = datetime(2026, 11, 9, 10, 40, tzinfo=timezone.utc)  # a Monday, 05:40 NY


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def ago(**kw):
    return _iso(NOW - timedelta(**kw))


STATES = [
    {"id": "s-backlog", "name": "Backlog", "type": "backlog"},
    {"id": "s-todo", "name": "Todo", "type": "unstarted"},
    {"id": "s-prog", "name": "In Progress", "type": "started"},
    {"id": "s-done", "name": "Done", "type": "completed"},
    {"id": "s-canc", "name": "Canceled", "type": "canceled"},
    {"id": "s-dup", "name": "Duplicate", "type": "duplicate"},
]
LABELS = [
    {"id": "l-held", "name": "parked:held"},
    {"id": "l-def", "name": "parked:deferred"},
    {"id": "l-feat", "name": "Feature"},
]
PROJECTS = [{"id": "p-lab", "name": "Weyland Lab"}, {"id": "p-studio", "name": "Stud.IO"}]


def issue(ident, *, project="p-lab", state="s-backlog", priority=3, labels=(), created=None, updated=None,
          completed=None, canceled=None, archived=None, title=None):
    return {"id": ident, "identifier": ident, "title": title or f"title {ident}", "project": {"id": project},
            "state": {"id": state}, "priority": priority, "labelIds": list(labels),
            "createdAt": created or ago(days=100), "updatedAt": updated or ago(days=1),
            "completedAt": completed, "canceledAt": canceled, "archivedAt": archived}


def snap(*issues):
    return {"issues": list(issues), "workflowStates": STATES, "issueLabels": LABELS, "projects": PROJECTS}


# ── freshness ──────────────────────────────────────────────────────────────────────────────────────────────────────

def test_a_fresh_snapshot_passes_and_reports_its_age(linear_digest):
    age = linear_digest.check_fresh({"finished_at": _iso(NOW - timedelta(hours=5))}, NOW)
    assert 4.9 < age < 5.1


def test_a_snapshot_older_than_26h_is_refused(linear_digest):
    with pytest.raises(linear_digest.DigestError, match="older than 26 h"):
        linear_digest.check_fresh({"finished_at": _iso(NOW - timedelta(hours=27))}, NOW)


def test_a_manifest_without_finished_at_is_refused_never_assumed_fresh(linear_digest):
    with pytest.raises(linear_digest.DigestError, match="finished_at"):
        linear_digest.check_fresh({}, NOW)


# ── the digest ─────────────────────────────────────────────────────────────────────────────────────────────────────

def test_closed_counts_done_and_canceled_inside_the_window_only(linear_digest):
    d = linear_digest.build_digest(snap(
        issue("EMA-1", state="s-done", completed=ago(days=2)),
        issue("EMA-2", state="s-canc", canceled=ago(days=3)),
        issue("EMA-3", state="s-dup", canceled=ago(days=1)),
        issue("EMA-4", state="s-done", completed=ago(days=9)),   # before the window
    ), NOW)
    # chronological, oldest first: EMA-2 closed 3 days ago, EMA-1 2 days ago, EMA-3 1 day ago
    assert [i["identifier"] for i in d["closed"]] == ["EMA-2", "EMA-1", "EMA-3"]
    assert {i["identifier"]: i["state"] for i in d["closed"]}["EMA-2"] == "Canceled"


def test_opened_is_created_inside_the_window_whatever_its_state_now(linear_digest):
    d = linear_digest.build_digest(snap(
        issue("EMA-10", created=ago(days=1)),
        issue("EMA-11", created=ago(days=6), state="s-done", completed=ago(days=5)),
        issue("EMA-12", created=ago(days=8)),
    ), NOW)
    assert sorted(i["identifier"] for i in d["opened"]) == ["EMA-10", "EMA-11"]


def test_the_high_lane_is_open_priority_2_with_hold_labels_shown(linear_digest):
    d = linear_digest.build_digest(snap(
        issue("EMA-20", priority=2, labels=["l-held", "l-feat"]),
        issue("EMA-21", priority=2, state="s-prog"),
        issue("EMA-22", priority=2, state="s-done", completed=ago(days=20)),   # closed: not in the lane
        issue("EMA-23", priority=3),                                            # not High
        issue("EMA-24", priority=2, archived=ago(days=1)),                      # archived: not in the lane
    ), NOW)
    lane = {i["identifier"]: i["holds"] for i in d["high"]}
    assert lane == {"EMA-20": ["parked:held"], "EMA-21": []}


def test_stale_is_open_and_untouched_30_days_with_a_count_and_the_oldest_5(linear_digest):
    stale = [issue(f"EMA-3{n}", updated=ago(days=31 + n)) for n in range(7)]
    d = linear_digest.build_digest(snap(
        *stale,
        issue("EMA-40", updated=ago(days=29)),                                    # not stale yet
        issue("EMA-41", updated=ago(days=90), state="s-done", completed=ago(days=90)),  # closed: never stale
    ), NOW)
    assert d["stale_count"] == 7
    assert [i["identifier"] for i in d["stale_oldest"]] == ["EMA-36", "EMA-35", "EMA-34", "EMA-33", "EMA-32"]


def test_other_projects_never_leak_into_any_list(linear_digest):
    d = linear_digest.build_digest(snap(
        issue("EMA-50", project="p-studio", state="s-done", completed=ago(days=1), created=ago(days=1)),
        issue("EMA-51", project="p-studio", priority=2),
        issue("EMA-52", project="p-studio", updated=ago(days=60)),
    ), NOW)
    assert d["closed"] == d["opened"] == d["high"] == [] and d["stale_count"] == 0


def test_an_unknown_project_is_an_error_not_an_empty_digest(linear_digest):
    with pytest.raises(linear_digest.DigestError, match="Nowhere"):
        linear_digest.build_digest(snap(issue("EMA-60")), NOW, project="Nowhere")


# ── the Slack message ──────────────────────────────────────────────────────────────────────────────────────────────

def _text(payload):
    return payload["text"] + "\n" + "\n".join(b.get("text", {}).get("text", "") for b in payload["blocks"])


def test_a_quiet_week_still_sends_with_zero_counts(linear_digest):
    payload = linear_digest.format_slack(linear_digest.build_digest(snap(), NOW))
    body = _text(payload)
    assert "Weekly Linear digest" in body
    assert "nothing closed" in body.lower()
    assert "Closed (0)" in body and "Opened (0)" in body and "Stale 30+ days (0)" in body


def test_long_lists_are_truncated_with_plus_n_more_and_the_counts_survive(linear_digest):
    many = [issue(f"EMA-{100 + n}", state="s-done", completed=ago(days=1)) for n in range(25)]
    body = _text(linear_digest.format_slack(linear_digest.build_digest(snap(*many), NOW), max_items=10))
    assert "Closed (25)" in body
    assert "+15 more" in body


def test_every_section_stays_inside_slacks_3000_character_limit(linear_digest):
    long_title = "x" * 900
    many = [issue(f"EMA-{200 + n}", priority=2, title=long_title) for n in range(20)]
    payload = linear_digest.format_slack(linear_digest.build_digest(snap(*many), NOW), max_items=20)
    sections = [b["text"]["text"] for b in payload["blocks"] if b.get("type") == "section"]
    assert sections and all(len(s) <= 3000 for s in sections)
    assert "High lane (20)" in _text(payload)


def test_the_message_says_which_snapshot_and_window_it_covers(linear_digest):
    d = linear_digest.build_digest(snap(), NOW)
    body = _text(linear_digest.format_slack(d, snapshot="2026-11-09T102015Z"))
    assert "2026-11-09T102015Z" in body and "2026-11-02" in body


# ── posting ────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_post_accepts_only_200_with_body_ok(linear_digest):
    seen = {}

    def send(url, body):
        seen["url"], seen["body"] = url, body
        return 200, "ok"

    linear_digest.post("https://hooks.example/x", {"text": "t"}, send=send)
    assert seen["url"] == "https://hooks.example/x" and b'"text"' in seen["body"]


@pytest.mark.parametrize("status,body", [(200, "no_text"), (404, "no_service"), (500, "")])
def test_post_fails_on_anything_but_200_ok(linear_digest, status, body):
    with pytest.raises(linear_digest.DigestError, match="Slack"):
        linear_digest.post("https://hooks.example/x", {"text": "t"}, send=lambda u, b: (status, body))


def test_a_post_failure_never_echoes_the_webhook_url(linear_digest):
    with pytest.raises(linear_digest.DigestError) as e:
        linear_digest.post("https://hooks.slack.com/services/SECRET/PATH", {"text": "t"},
                           send=lambda u, b: (403, "invalid_token"))
    assert "SECRET" not in str(e.value)


def test_an_empty_webhook_url_is_refused_before_any_send(linear_digest):
    def send(url, body):
        raise AssertionError("must not send")

    with pytest.raises(linear_digest.DigestError, match="SLACK_WEBHOOK_LINEAR_UPDATES"):
        linear_digest.post("", {"text": "t"}, send=send)


# ── B119.1: the My Work section (owner, 2026-11-11) ────────────────────────────────────────────────────────────────
# My Work is a to-do list, not an objective: each week the digest lists its projects with their last activity, and a
# project idle for 6 months (no Linear activity AND no commit) while new work kept arriving elsewhere is flagged
# "retire or recommit?". Commit times come from GitHub (pushed_at) via the asset; ``pushed=None`` means unknown.
# Shapes follow linear_tables.py: links are {"initiative": {"id"}, "project": {"id"}}, updates {"project": {"id"}}.

MW_PROJECTS = [{"id": "p-blog", "name": "blog", "updatedAt": ago(days=400)},
               {"id": "p-algo", "name": "Algopedia", "updatedAt": ago(days=400)},
               {"id": "p-lab", "name": "Weyland Lab", "updatedAt": ago(days=1)}]
MW_INITIATIVES = [{"id": "i-mw", "name": "My Work"}, {"id": "i-lab", "name": "Lab and Systems"}]


def mw_snap(*issues, updates=()):
    return {"issues": list(issues), "workflowStates": STATES, "issueLabels": LABELS, "projects": MW_PROJECTS,
            "initiatives": list(MW_INITIATIVES),
            "initiativeToProjects": [{"initiative": {"id": "i-mw"}, "project": {"id": "p-blog"}},
                                     {"initiative": {"id": "i-mw"}, "project": {"id": "p-algo"}},
                                     {"initiative": {"id": "i-lab"}, "project": {"id": "p-lab"}}],
            "projectUpdates": list(updates)}


def _pushed(blog_days, algo_days):
    return {"blog": NOW - timedelta(days=blog_days), "Algopedia": NOW - timedelta(days=algo_days)}


def test_my_work_lists_every_project_with_its_last_activity(linear_digest):
    rows = linear_digest.my_work(mw_snap(issue("EMA-9", project="p-blog", updated=ago(days=20))), NOW,
                                 pushed=_pushed(3, 50))
    by = {r["project"]: r for r in rows}
    assert set(by) == {"blog", "Algopedia"}                        # only My Work's projects
    assert by["blog"]["last_activity"] == (NOW - timedelta(days=3)).date().isoformat()   # the commit is newer
    assert by["Algopedia"]["idle_days"] == 50 and not by["Algopedia"]["retire"]


def test_idle_six_months_while_other_work_arrives_is_flagged_retire(linear_digest):
    snap_ = mw_snap(issue("EMA-1", project="p-lab", created=ago(days=30)))   # new work elsewhere since blog went idle
    by = {r["project"]: r for r in linear_digest.my_work(snap_, NOW, pushed=_pushed(200, 10))}
    assert by["blog"]["retire"] and by["blog"]["idle_days"] == 200
    assert not by["Algopedia"]["retire"]


def test_idle_six_months_with_no_new_work_anywhere_is_not_flagged(linear_digest):
    snap_ = mw_snap(issue("EMA-1", project="p-lab", created=ago(days=300)))  # nothing created since the blog went idle
    by = {r["project"]: r for r in linear_digest.my_work(snap_, NOW, pushed=_pushed(200, 10))}
    assert not by["blog"]["retire"]


def test_unknown_commit_data_never_raises_a_retire_flag(linear_digest):
    # GitHub unreachable: idle by Linear alone is not proof — a repo can be busy with commits and no issues.
    rows = linear_digest.my_work(mw_snap(issue("EMA-1", project="p-lab", created=ago(days=5))), NOW, pushed=None)
    assert rows and all(not r["retire"] and r["commits_known"] is False for r in rows)


def test_a_project_update_counts_as_activity(linear_digest):
    snap_ = mw_snap(issue("EMA-1", project="p-lab", created=ago(days=5)),
                    updates=[{"project": {"id": "p-blog"}, "createdAt": ago(days=4)}])
    by = {r["project"]: r for r in linear_digest.my_work(snap_, NOW, pushed=_pushed(300, 1))}
    assert not by["blog"]["retire"] and by["blog"]["idle_days"] == 4


def test_an_unknown_initiative_is_refused(linear_digest):
    snap_ = mw_snap()
    snap_["initiatives"] = [{"id": "i-lab", "name": "Lab and Systems"}]
    with pytest.raises(linear_digest.DigestError, match="My Work"):
        linear_digest.my_work(snap_, NOW, pushed={})


def test_the_slack_message_carries_my_work_and_flags_retire(linear_digest):
    d = linear_digest.build_digest(snap(issue("EMA-1")), NOW)
    rows = [{"project": "blog", "last_activity": "2026-04-01", "idle_days": 222, "retire": True, "commits_known": True},
            {"project": "Algopedia", "last_activity": "2026-11-01", "idle_days": 8, "retire": False,
             "commits_known": True}]
    payload = linear_digest.format_slack(d, my_work=rows)
    text = str(payload["blocks"])
    assert "My Work" in text and "blog" in text and "retire or recommit" in text
    assert "retire 1" in payload["text"]


def test_okr_gaps_lists_active_initiatives_without_an_okr_section(linear_digest):
    s = {"initiatives": [{"name": "A", "status": "Active", "content": "scope\n\n## OKR (Q4 2026)\n\nObjective: x"},
                         {"name": "B", "status": "Active", "content": "scope only"},
                         {"name": "C", "status": "Completed", "content": "old"},
                         {"name": "D", "status": "Active", "content": None}]}
    assert linear_digest.okr_gaps(s) == ["B", "D"]


def test_the_slack_message_names_initiatives_missing_okrs(linear_digest):
    d = linear_digest.build_digest(snap(issue("EMA-1")), NOW)
    payload = linear_digest.format_slack(d, my_work=[], okr_missing=["Learning"])
    assert "Learning" in str(payload["blocks"]) and "OKR" in str(payload["blocks"])
    assert "OKR" not in str(linear_digest.format_slack(d, my_work=[], okr_missing=[])["blocks"])


REPOS = [{"name": "grkit", "linear_project": "grkit"}, {"name": "Algopedia", "linear_project": "Algopedia"},
         {"name": "weyland-lab", "linear_project": "Weyland Lab"}, {"name": "midi_real_book"}]


def test_pushed_times_maps_projects_to_their_repos_last_push(linear_digest):
    calls = []

    def get_json(url):
        calls.append(url)
        return {"pushed_at": "2026-11-01T12:00:00Z"}

    got = linear_digest.pushed_times(REPOS, {"grkit", "Algopedia"}, get_json)
    assert got == {"grkit": datetime(2026, 11, 1, 12, tzinfo=timezone.utc),
                   "Algopedia": datetime(2026, 11, 1, 12, tzinfo=timezone.utc)}
    assert sorted(calls) == ["https://api.github.com/repos/edtbl76/Algopedia",
                             "https://api.github.com/repos/edtbl76/grkit"]     # only the projects asked for


@pytest.mark.parametrize("bad", [lambda u: (_ for _ in ()).throw(OSError("down")), lambda u: {}, lambda u: None])
def test_pushed_times_is_unknown_on_any_failure_or_missing_value(linear_digest, bad):
    assert linear_digest.pushed_times(REPOS, {"grkit"}, bad) is None


def test_pushed_times_is_unknown_when_a_project_has_no_repo(linear_digest):
    assert linear_digest.pushed_times(REPOS, {"grkit", "Service Transformation"}, lambda u: {"pushed_at": "x"}) is None


def test_the_slack_message_says_when_commit_data_is_unknown(linear_digest):
    d = linear_digest.build_digest(snap(issue("EMA-1")), NOW)
    rows = [{"project": "blog", "last_activity": "2026-04-01", "idle_days": 222, "retire": False,
             "commits_known": False}]
    assert "commit activity unknown" in str(linear_digest.format_slack(d, my_work=rows)["blocks"])
