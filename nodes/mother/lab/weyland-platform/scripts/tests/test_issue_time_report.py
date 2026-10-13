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


def _states(tmp_path):
    p = tmp_path / "workflowStates.json"
    p.write_text(json.dumps([{"id": "s-prog", "name": "In Progress", "type": "started"}]))
    return str(p)


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
        r.main(["--sessions", sess, "--states", _states(tmp_path), "--issues", str(bad)])
    assert e.value.code == 2 and "snapshot" in capsys.readouterr().err


def test_an_empty_snapshot_exits_2(tmp_path, capsys):
    sess = _write_sessions(tmp_path, [{"B1": _bucket(6, "2026-10-01T00:00:00Z")}])
    with pytest.raises(SystemExit) as e:
        r.main(["--sessions", sess, "--states", _states(tmp_path), "--issues", _write_snapshot(tmp_path, [])])
    assert e.value.code == 2 and "no issues" in capsys.readouterr().err


def test_an_unreadable_session_file_exits_2_naming_it(tmp_path, capsys):
    # Found by running the demo's negative case (2026-10-12): a non-summary .json crashed with a traceback and exit 1.
    d = tmp_path / "sessions"
    d.mkdir()
    (d / "broken.json").write_text("{not json")
    with pytest.raises(SystemExit) as e:
        r.main(["--sessions", str(d), "--states", _states(tmp_path), "--issues", _write_snapshot(tmp_path, [_issue("EMA-1", "B1 — a")])])
    assert e.value.code == 2 and "broken.json" in capsys.readouterr().err


def test_sessions_without_attribution_exit_2(tmp_path, capsys):
    d = tmp_path / "old"
    d.mkdir()
    (d / "s.json").write_text(json.dumps({"session_id": "s"}))        # a pre-B185 summary: no issues{}
    with pytest.raises(SystemExit) as e:
        r.main(["--sessions", str(d), "--states", _states(tmp_path), "--issues", _write_snapshot(tmp_path, [_issue("EMA-1", "B1 — a")])])
    assert e.value.code == 2 and "attribution" in capsys.readouterr().err


def test_main_prints_a_table_or_json(tmp_path, capsys):
    snap = _write_snapshot(tmp_path, [_issue("EMA-237", "B179 — Software-factory experiments")])
    sess = _write_sessions(tmp_path, [{"B179": _bucket(90, "2026-10-05T10:00:00Z")}])
    assert r.main(["--sessions", sess, "--states", _states(tmp_path), "--issues", snap]) == 0
    out = capsys.readouterr().out
    assert "EMA-237" in out and "B179" in out and "1.5" in out
    assert r.main(["--sessions", sess, "--states", _states(tmp_path), "--issues", snap, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["issue"] == "EMA-237"


# --- Port view (2026-10-13): one `issue_time` entity per issue, related to the Linear integration's `linearIssue` -----
# The blueprint is ours (tofu/port/issue_time.tf); linearIssue is integration-owned (port.md B137), so the time lives
# beside it, not on it. Shapes OBSERVED 2026-10-13: entity upsert POST /v1/blueprints/<bp>/entities?upsert=true&merge=true;
# dashboard pages as GET /v1/pages/code_health returned them ({"page": {..., "widgets": [{"type": "dashboard-widget"}]}}).

class FakePort:
    """Records requests; serves GET entities from what was upserted (or a preset)."""

    def __init__(self, existing=None, page_exists=True, corrupt=None, fail=None, linear=("EMA-237", "EMA-92", "EMA-95")):
        self.store = {e["identifier"]: e for e in (existing or [])}
        self.linear = linear
        self.page_exists, self.corrupt, self.fail = page_exists, corrupt or {}, fail
        self.calls = []

    def request(self, method, path, body=None):
        self.calls.append((method, path, body))
        if self.fail and self.fail in path:
            raise r.InputError(f"{method} {path} -> HTTP 500")
        if method == "POST" and path.startswith("/v1/blueprints/issue_time/entities"):
            e = dict(body)
            e["properties"] = {**e["properties"], **self.corrupt.get(e["identifier"], {})}
            self.store[e["identifier"]] = e
            return {"ok": True}
        if method == "GET" and path.startswith("/v1/blueprints/linearIssue/entities"):
            return {"entities": [{"identifier": i} for i in self.linear]}
        if method == "GET" and path.startswith("/v1/blueprints/issue_time/entities"):
            return {"entities": list(self.store.values())}
        if method == "DELETE" and path.startswith("/v1/blueprints/issue_time/entities/"):
            self.store.pop(path.rsplit("/", 1)[1].split("?")[0])
            return {"ok": True}
        if path.startswith("/v1/pages"):
            if method == "GET":
                if not self.page_exists:
                    raise r.NotFound(path)
                return {"page": {"identifier": "time_per_issue"}}
            # OBSERVED 2026-10-13 (the second live push): PATCH /v1/pages/<id> answers 422 'Unrecognized keys: "type",
            # "sidebar"' — those are create-only. The first push had created the page with POST, so only a re-run hit it.
            if method == "PATCH" and {"type", "sidebar"} & set(body):
                raise r.InputError(f"PATCH {path} -> HTTP 422: Unrecognized keys")
            return {"ok": True}
        raise AssertionError(f"unexpected {method} {path}")


def _rows(tmp_path):
    snap = _write_snapshot(tmp_path, [
        _issue("EMA-237", "B179 — conveyor", created="2026-10-01T00:00:00Z", completed="2026-10-12T00:00:00Z"),
        _issue("EMA-92", "B101 — x", archived="2026-09-01T00:00:00Z"),
        _issue("EMA-95", "B101 — y", archived="2026-09-01T00:00:00Z")])
    sess = _write_sessions(tmp_path, [{"B179": _bucket(228, "2026-10-05T10:00:00Z", out=285520, usd=12.5),
                                       "B101": _bucket(30, "2026-10-01T00:00:00Z")}])
    return r.build(r.load_sessions(sess), r.load_issues(snap))


def test_port_entities_relate_mapped_issues_and_never_guess_an_unmapped_one(tmp_path):
    ents = {e["identifier"]: e for e in r.port_entities(_rows(tmp_path), {"EMA-237"})}
    e = ents["EMA-237"]
    assert e["title"] == "EMA-237 · B179" and e["relations"] == {"issue": "EMA-237"}
    assert e["properties"]["agent_hours"] == 3.8 and e["properties"]["output_tokens"] == 285520
    assert e["properties"]["backlog"] == "B179" and e["properties"]["lead_days"] == 11.0
    assert ents["B101"]["relations"] == {} and ents["B101"]["properties"]["unmapped"] is True


def test_push_upserts_verifies_and_deletes_stale_entities(tmp_path, capsys):
    port = FakePort(existing=[{"identifier": "B179", "properties": {}, "relations": {}}])  # since mapped to EMA-237
    assert r.push_to_port(_rows(tmp_path), port) == 0
    assert set(port.store) == {"EMA-237", "B101"}
    posts = [c for c in port.calls if c[0] == "POST" and "entities" in c[1]]
    assert all("upsert=true" in p[1] and "merge=true" in p[1] for p in posts)
    assert ("DELETE", "/v1/blueprints/issue_time/entities/B179", None) in port.calls
    assert "port: 2 issue_time entities upserted and read back, 1 stale deleted" in capsys.readouterr().out


def test_push_fails_on_a_read_back_that_does_not_match(tmp_path, capsys):
    port = FakePort(corrupt={"EMA-237": {"agent_hours": 0}})
    assert r.push_to_port(_rows(tmp_path), port) == 1
    assert "EMA-237: agent_hours" in capsys.readouterr().err


def test_push_creates_the_dashboard_when_absent_and_updates_it_when_present(tmp_path):
    rows = _rows(tmp_path)
    for exists, verb in ((False, "POST"), (True, "PATCH")):
        port = FakePort(page_exists=exists)
        assert r.push_to_port(rows, port) == 0
        page_writes = [c for c in port.calls if c[1].startswith("/v1/pages") and c[0] in ("POST", "PATCH")]
        assert [c[0] for c in page_writes] == [verb]
        assert page_writes[0][2]["identifier"] == "time_per_issue"


def test_the_dashboard_in_git_tables_the_issue_time_blueprint():
    page = r.dashboard_page()
    assert page["identifier"] == "time_per_issue" and page["type"] == "dashboard"
    widgets = page["widgets"][0]["widgets"]
    assert any(w["type"] == "table-entities-explorer" and w["blueprint"] == "issue_time" for w in widgets)
    ids = {w["id"] for w in widgets}
    assert {c["id"] for row in page["widgets"][0]["layout"] for c in row["columns"]} == ids  # layout names real widgets


def test_a_port_api_failure_is_exit_2(tmp_path, capsys):
    port = FakePort(fail="/v1/blueprints/issue_time/entities")
    assert r.push_to_port(_rows(tmp_path), port) == 2
    assert "HTTP 500" in capsys.readouterr().err


def test_main_port_without_credentials_exits_2(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("PORT_CLIENT_ID", raising=False)
    monkeypatch.delenv("PORT_CLIENT_SECRET", raising=False)
    snap = _write_snapshot(tmp_path, [_issue("EMA-237", "B179 — x")])
    sess = _write_sessions(tmp_path, [{"B179": _bucket(60, "2026-10-05T10:00:00Z")}])
    with pytest.raises(SystemExit) as e:
        r.main(["--sessions", sess, "--states", _states(tmp_path), "--issues", snap, "--port"])
    assert e.value.code == 2 and "PORT_CLIENT_ID" in capsys.readouterr().err


def test_an_issue_port_does_not_know_keeps_its_time_without_a_relation(tmp_path, capsys):
    # Observed 2026-10-13 (first live push): EMA-206 has no linearIssue entity in Port (the integration does not sync
    # it), Port answered 404 to the relation, and the whole push stopped. Its time still belongs in the catalog.
    port = FakePort(linear=())
    assert r.push_to_port(_rows(tmp_path), port) == 0
    assert port.store["EMA-237"]["relations"] == {}
    assert "1 without a linearIssue in Port: EMA-237" in capsys.readouterr().out


# --- the Linear start, defined as the B194 dbt mart defines it (2026-10-13) ----------------------------------------
# mart_linear_issue_cycle_time.sql: started_at = coalesce(startedAt, first history transition into a `started`-type
# state). The report used startedAt alone, so the lab had two cycle-time definitions (4 issues differed). Shapes
# OBSERVED in 2026-10-13T092012Z: issue.history = {"nodes": [{"createdAt", "toStateId", …}], "pageInfo":
# {"hasNextPage": false}}; workflowStates.json.gz = [{"id", "name", "type": "started" | "completed" | …}].
STATES = [{"id": "s-prog", "name": "In Progress", "type": "started"}, {"id": "s-todo", "name": "Todo", "type": "unstarted"},
          {"id": "s-done", "name": "Done", "type": "completed"}]


def _with_history(issue, *moves):
    issue["history"] = {"nodes": [{"createdAt": t, "toStateId": s} for t, s in moves],
                        "pageInfo": {"hasNextPage": False}}
    return issue


def test_without_started_at_the_first_started_transition_is_the_linear_start(tmp_path):
    snap = _write_snapshot(tmp_path, [_with_history(
        _issue("EMA-1", "B1 — a", created="2026-10-01T00:00:00Z", completed="2026-10-05T00:00:00Z"),
        ("2026-10-02T00:00:00Z", "s-todo"), ("2026-10-03T00:00:00Z", "s-prog"), ("2026-10-05T00:00:00Z", "s-done"))])
    sess = _write_sessions(tmp_path, [{"B1": _bucket(6, "2026-10-04T00:00:00Z")}])
    row = r.build(r.load_sessions(sess), r.load_issues(snap), r.started_state_ids(STATES))[0]
    assert row["cycle_days"] == 2.0                    # the 10-03 move into In Progress, earlier than the agent (10-04)


def test_started_at_wins_over_history_as_in_the_mart(tmp_path):
    snap = _write_snapshot(tmp_path, [_with_history(
        _issue("EMA-1", "B1 — a", created="2026-10-01T00:00:00Z", started="2026-10-04T00:00:00Z",
               completed="2026-10-05T00:00:00Z"),
        ("2026-10-02T00:00:00Z", "s-prog"))])
    sess = _write_sessions(tmp_path, [{"B1": _bucket(6, "2026-10-04T12:00:00Z")}])
    row = r.build(r.load_sessions(sess), r.load_issues(snap), r.started_state_ids(STATES))[0]
    assert row["cycle_days"] == 1.0                    # coalesce(startedAt, history): startedAt 10-04 stands


def test_the_states_file_must_name_a_started_state(tmp_path):
    p = tmp_path / "workflowStates.json"
    p.write_text(json.dumps([{"id": "x", "type": "completed"}]))
    with pytest.raises(r.InputError, match="started"):
        r.load_states(str(p))
