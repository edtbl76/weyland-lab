"""Tests for issue_time_report.py — B185 lane 1: agent time per Linear issue, plus lead and cycle time.

Inputs are the feeder's per-session JSONs (`issues{}` per session) and a B194 Linear snapshot (`issues.json.gz`, a JSON
list). The snapshot fields used here were OBSERVED in 2026-10-12T092015Z: `identifier`, `title` ("B205 — …"),
`createdAt`, `startedAt` (null on 241 of 292), `completedAt`, `archivedAt`; two B numbers map to two issues each, all archived.
"""
import gzip
import json

import pytest

import issue_time_report as r


def _issue(ident, title, created="2026-10-01T00:00:00.000Z", started=None, completed=None, archived=None):
    return {"identifier": ident, "title": title, "createdAt": created, "startedAt": started,
            "completedAt": completed, "archivedAt": archived}


def _bucket(minutes, first_at, out=0, usd=0.0):
    return {"active_minutes": minutes, "output_tokens": out, "api_equiv_value_usd": usd, "assistant_turns": 1,
            "first_at": first_at}


def _write_sessions(tmp_path, sessions):
    d = tmp_path / "sessions"
    d.mkdir()
    for i, issues in enumerate(sessions):
        (d / f"s{i}.json").write_text(json.dumps({"session_id": f"s{i}", "issues": issues}))
    return str(d)


def _write_snapshot(tmp_path, issues, gz=True):
    p = tmp_path / ("issues.json.gz" if gz else "issues.json")
    data = json.dumps(issues).encode()
    p.write_bytes(gzip.compress(data) if gz else data)
    return str(p)


def test_b_numbers_map_to_their_linear_issue_and_merge_with_ema_ids(tmp_path):
    snap = _write_snapshot(tmp_path, [_issue("EMA-237", "B179 — Software-factory experiments")])
    sess = _write_sessions(tmp_path, [
        {"B179": _bucket(60, "2026-10-05T10:00:00Z", out=100, usd=1.0)},
        {"EMA-237": _bucket(30, "2026-10-04T10:00:00Z", out=50, usd=0.5)}])
    rows = r.build(r.load_sessions(sess), r.load_issues(snap))
    assert len(rows) == 1
    row = rows[0]
    assert row["issue"] == "EMA-237" and row["backlog"] == "B179"
    assert row["agent_hours"] == 1.5 and row["output_tokens"] == 150 and row["api_equiv_usd"] == 1.5
    assert row["sessions"] == 2 and row["first_agent_at"] == "2026-10-04T10:00:00Z"


def test_lead_time_and_cycle_time_from_the_earlier_of_started_and_first_agent_activity(tmp_path):
    snap = _write_snapshot(tmp_path, [
        _issue("EMA-1", "B1 — a", created="2026-10-01T00:00:00Z", started="2026-10-03T00:00:00Z",
               completed="2026-10-05T00:00:00Z"),
        _issue("EMA-2", "B2 — b", created="2026-10-01T00:00:00Z", started=None, completed="2026-10-05T00:00:00Z")])
    sess = _write_sessions(tmp_path, [{"B1": _bucket(6, "2026-10-02T00:00:00Z"),
                                       "B2": _bucket(6, "2026-10-04T12:00:00Z")}])
    rows = {x["issue"]: x for x in r.build(r.load_sessions(sess), r.load_issues(snap))}
    assert rows["EMA-1"]["lead_days"] == 4.0
    assert rows["EMA-1"]["cycle_days"] == 3.0          # agent work (10-02) began before Linear's startedAt (10-03)
    assert rows["EMA-2"]["cycle_days"] == 0.5          # no startedAt (241 of 292 lack one): the agent start stands


def test_agent_activity_after_completion_never_starts_the_cycle(tmp_path):
    # Observed 2026-10-12: B152 (EMA-209) was named in a prompt ten days after it closed, giving cycle_days = -10.6.
    snap = _write_snapshot(tmp_path, [
        _issue("EMA-1", "B1 — a", created="2026-10-01T00:00:00Z", started="2026-10-02T00:00:00Z",
               completed="2026-10-04T00:00:00Z"),
        _issue("EMA-2", "B2 — b", created="2026-10-01T00:00:00Z", completed="2026-10-04T00:00:00Z")])
    sess = _write_sessions(tmp_path, [{"B1": _bucket(6, "2026-10-14T00:00:00Z"),
                                       "B2": _bucket(6, "2026-10-14T00:00:00Z")}])
    rows = {x["issue"]: x for x in r.build(r.load_sessions(sess), r.load_issues(snap))}
    assert rows["EMA-1"]["cycle_days"] == 2.0          # Linear's startedAt stands
    assert rows["EMA-2"]["cycle_days"] is None         # no start known before completion: unknown, not negative
    assert rows["EMA-2"]["agent_hours"] == 0.1         # the later work still counts as agent time


def test_an_open_issue_has_no_lead_or_cycle_time(tmp_path):
    snap = _write_snapshot(tmp_path, [_issue("EMA-243", "B185 — time per issue")])
    sess = _write_sessions(tmp_path, [{"B185": _bucket(12, "2026-10-12T10:00:00Z")}])
    row = r.build(r.load_sessions(sess), r.load_issues(snap))[0]
    assert row["lead_days"] is None and row["cycle_days"] is None and row["agent_hours"] == 0.2


def test_a_b_number_on_two_issues_prefers_the_unarchived_one_else_stays_unmapped(tmp_path):
    snap = _write_snapshot(tmp_path, [
        _issue("EMA-10", "B50 — old", archived="2026-09-01T00:00:00Z"), _issue("EMA-11", "B50 — current"),
        _issue("EMA-95", "B101 — x", archived="2026-09-01T00:00:00Z"),
        _issue("EMA-92", "B101 — y", archived="2026-09-01T00:00:00Z")])
    sess = _write_sessions(tmp_path, [{"B50": _bucket(6, "2026-10-01T00:00:00Z"),
                                       "B101": _bucket(6, "2026-10-01T00:00:00Z")}])
    rows = {x["issue"]: x for x in r.build(r.load_sessions(sess), r.load_issues(snap))}
    assert rows["EMA-11"]["backlog"] == "B50"
    assert rows["B101"]["unmapped"] is True            # ambiguous: shown under its B number, never guessed


def test_a_sub_item_number_maps_on_its_own(tmp_path):
    snap = _write_snapshot(tmp_path, [_issue("EMA-300", "B86.1 — Spec bake-off"), _issue("EMA-301", "B86 — parent")])
    sess = _write_sessions(tmp_path, [{"B86.1": _bucket(6, "2026-10-01T00:00:00Z")}])
    assert [x["issue"] for x in r.build(r.load_sessions(sess), r.load_issues(snap))] == ["EMA-300"]


def test_rows_are_sorted_by_agent_time_descending(tmp_path):
    snap = _write_snapshot(tmp_path, [_issue("EMA-1", "B1 — a"), _issue("EMA-2", "B2 — b")])
    sess = _write_sessions(tmp_path, [{"B1": _bucket(6, "2026-10-01T00:00:00Z"),
                                       "B2": _bucket(60, "2026-10-01T00:00:00Z")}])
    assert [x["issue"] for x in r.build(r.load_sessions(sess), r.load_issues(snap))] == ["EMA-2", "EMA-1"]


def test_a_plain_json_snapshot_also_loads(tmp_path):
    assert r.load_issues(_write_snapshot(tmp_path, [_issue("EMA-1", "B1 — a")], gz=False))[0]["identifier"] == "EMA-1"


# --- fail closed: an absent or unreadable input is never an empty report ------------------------------------------

def test_an_unreadable_snapshot_exits_2_and_says_why(tmp_path, capsys):
    bad = tmp_path / "issues.json.gz"
    bad.write_bytes(b"not gzip, not json")
    sess = _write_sessions(tmp_path, [{"B1": _bucket(6, "2026-10-01T00:00:00Z")}])
    with pytest.raises(SystemExit) as e:
        r.main(["--sessions", sess, "--issues", str(bad)])
    assert e.value.code == 2 and "snapshot" in capsys.readouterr().err


def test_an_empty_snapshot_exits_2(tmp_path, capsys):
    sess = _write_sessions(tmp_path, [{"B1": _bucket(6, "2026-10-01T00:00:00Z")}])
    with pytest.raises(SystemExit) as e:
        r.main(["--sessions", sess, "--issues", _write_snapshot(tmp_path, [])])
    assert e.value.code == 2 and "no issues" in capsys.readouterr().err


def test_an_unreadable_session_file_exits_2_naming_it(tmp_path, capsys):
    # Found by running the demo's negative case (2026-10-12): a non-summary .json crashed with a traceback and exit 1.
    d = tmp_path / "sessions"
    d.mkdir()
    (d / "broken.json").write_text("{not json")
    with pytest.raises(SystemExit) as e:
        r.main(["--sessions", str(d), "--issues", _write_snapshot(tmp_path, [_issue("EMA-1", "B1 — a")])])
    assert e.value.code == 2 and "broken.json" in capsys.readouterr().err


def test_sessions_without_attribution_exit_2(tmp_path, capsys):
    d = tmp_path / "old"
    d.mkdir()
    (d / "s.json").write_text(json.dumps({"session_id": "s"}))        # a pre-B185 summary: no issues{}
    with pytest.raises(SystemExit) as e:
        r.main(["--sessions", str(d), "--issues", _write_snapshot(tmp_path, [_issue("EMA-1", "B1 — a")])])
    assert e.value.code == 2 and "attribution" in capsys.readouterr().err


def test_main_prints_a_table_or_json(tmp_path, capsys):
    snap = _write_snapshot(tmp_path, [_issue("EMA-237", "B179 — Software-factory experiments")])
    sess = _write_sessions(tmp_path, [{"B179": _bucket(90, "2026-10-05T10:00:00Z")}])
    assert r.main(["--sessions", sess, "--issues", snap]) == 0
    out = capsys.readouterr().out
    assert "EMA-237" in out and "B179" in out and "1.5" in out
    assert r.main(["--sessions", sess, "--issues", snap, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["issue"] == "EMA-237"
