"""Tests for linear_restore.py — rebuild issues + comments from a B194 Linear snapshot (B194 Slice 2, the DR drill).

The decisions are what these cover: refusing an incomplete snapshot (no manifest), restoring parents before children,
mapping states and labels onto the target team (and REPORTING what cannot be mapped, never silently dropping it), the
provenance header that records what the API cannot restore (original identifier, author, timestamps), threaded
comments, verification that compares a read-back against the snapshot, and a drill that tears down even when
verification fails. Node shapes are copied from a real snapshot (2026-09-27); the transport is a fake.
"""
import gzip
import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/ on path

import linear_restore as lr

TS = "2026-09-27T013914Z"


def _write_snapshot(tmp_path, entities, manifest=True):
    for name, nodes in entities.items():
        (tmp_path / f"{name}.json.gz").write_bytes(gzip.compress(json.dumps(nodes).encode()))
    if manifest:
        (tmp_path / "manifest.json").write_text(json.dumps({"format_version": 1, "started_at": "2026-09-27T01:39:14+00:00",
                                                           "counts": {k: len(v) for k, v in entities.items()}}))
    return str(tmp_path)


STATES = [
    {"id": "s-backlog", "name": "Backlog", "type": "backlog", "team": {"id": "t-ema"}},
    {"id": "s-done", "name": "Done", "type": "completed", "team": {"id": "t-ema"}},
    {"id": "s-review", "name": "In Review", "type": "started", "team": {"id": "t-ema"}},
]
LABELS = [
    {"id": "l-spike", "name": "Spike", "team": None, "archivedAt": None, "retiredAt": None, "isGroup": False},
    {"id": "l-team", "name": "parked:held", "team": {"id": "t-ema"}, "archivedAt": None, "retiredAt": None, "isGroup": False},
]
USERS = [{"id": "u-ed", "name": "Edward Mangini", "displayName": "emangini"}]
PARENT = {"id": "i-54", "identifier": "EMA-54", "title": "B57 — CI", "description": "Parent body", "priority": 2,
          "state": {"id": "s-done"}, "labelIds": ["l-spike"], "parent": None, "dueDate": None,
          "createdAt": "2026-07-01T10:00:00.000Z", "creator": {"id": "u-ed"}, "estimate": None,
          "project": {"id": "p-lab"}, "cycle": None, "archivedAt": None}
CHILD = {"id": "i-13", "identifier": "EMA-13", "title": "B17 — A2A", "description": None, "priority": 3,
         "state": {"id": "s-review"}, "labelIds": ["l-spike", "l-team"], "parent": {"id": "i-54"}, "dueDate": "2026-10-01",
         "createdAt": "2026-07-02T10:00:00.000Z", "creator": {"id": "u-ed"}, "estimate": 3,
         "project": None, "cycle": {"id": "c-1"}, "archivedAt": None}
COMMENTS = [
    {"id": "c-2", "body": "reply", "issue": {"id": "i-13"}, "parent": {"id": "c-1"}, "user": {"id": "u-ed"},
     "createdAt": "2026-07-03T11:00:00.000Z"},
    {"id": "c-1", "body": "root comment", "issue": {"id": "i-13"}, "parent": None, "user": {"id": "u-ed"},
     "createdAt": "2026-07-03T10:00:00.000Z"},
    {"id": "c-9", "body": "on another issue", "issue": {"id": "i-99"}, "parent": None, "user": {"id": "u-ed"},
     "createdAt": "2026-07-03T09:00:00.000Z"},
]


@pytest.fixture
def snap(tmp_path):
    d = _write_snapshot(tmp_path, {"issues": [CHILD, PARENT], "comments": COMMENTS, "workflowStates": STATES,
                                   "issueLabels": LABELS, "users": USERS})
    return lr.load_snapshot(d)


# --- loading + selection --------------------------------------------------------------------------------------

def test_load_refuses_a_snapshot_without_a_manifest(tmp_path):
    d = _write_snapshot(tmp_path, {"issues": [PARENT]}, manifest=False)
    with pytest.raises(lr.RestoreError, match="no manifest.json"):
        lr.load_snapshot(d)


def test_select_orders_parents_before_children_and_rejects_unknown_identifiers(snap):
    assert [i["identifier"] for i in lr.select_issues(snap, ["EMA-13", "EMA-54"])] == ["EMA-54", "EMA-13"]
    with pytest.raises(lr.RestoreError, match="EMA-404"):
        lr.select_issues(snap, ["EMA-404"])


# --- mapping ----------------------------------------------------------------------------------------------------

TARGET_STATES = [{"id": "n-backlog", "name": "Backlog", "type": "backlog"},
                 {"id": "n-progress", "name": "In Progress", "type": "started"},
                 {"id": "n-done", "name": "Done", "type": "completed"}]


def test_state_maps_by_name_then_falls_back_to_type(snap):
    m = lr.state_map(snap, TARGET_STATES)
    assert m["s-done"] == "n-done"            # same name
    assert m["s-review"] == "n-progress"      # "In Review" absent -> same type (started)


def test_issue_input_maps_fields_and_reports_what_it_dropped(snap):
    ctx = lr.RestoreContext(snapshot=snap, team_id="t-new", states=lr.state_map(snap, TARGET_STATES),
                            id_map={"i-54": "new-54"}, snapshot_ts=TS)
    inp, dropped = lr.build_issue_input(CHILD, ctx)
    assert inp["teamId"] == "t-new" and inp["title"] == "B17 — A2A" and inp["priority"] == 3
    assert inp["stateId"] == "n-progress" and inp["parentId"] == "new-54" and inp["dueDate"] == "2026-10-01"
    assert inp["labelIds"] == ["l-spike"]                      # workspace label kept by id
    assert "label parked:held (team-scoped)" in dropped         # team label cannot follow into another team
    assert "cycle" in dropped and "estimate" in dropped
    assert "estimate" not in inp                                # estimates are not used in this workspace


def test_description_carries_provenance_and_round_trips(snap):
    ctx = lr.RestoreContext(snapshot=snap, team_id="t", states={"s-done": "n-done"}, id_map={}, snapshot_ts=TS)
    inp, _ = lr.build_issue_input(PARENT, ctx)
    assert "EMA-54" in inp["description"] and "Edward Mangini" in inp["description"] and TS in inp["description"]
    assert lr.strip_provenance(inp["description"]) == "Parent body"


def test_empty_description_round_trips_to_empty(snap):
    ctx = lr.RestoreContext(snapshot=snap, team_id="t", states={"s-review": "n-progress"}, id_map={"i-54": "x"},
                            snapshot_ts=TS)
    inp, _ = lr.build_issue_input(CHILD, ctx)
    assert lr.strip_provenance(inp["description"]) == ""


def test_comments_for_issue_are_chronological_and_scoped(snap):
    assert [c["id"] for c in lr.comments_for(snap, "i-13")] == ["c-1", "c-2"]


def test_comment_input_maps_the_thread_parent_and_adds_provenance(snap):
    body_in = lr.build_comment_input(COMMENTS[0], "new-13", {"c-1": "new-c1"}, snap)
    assert body_in["issueId"] == "new-13" and body_in["parentId"] == "new-c1"
    assert "Edward Mangini" in body_in["body"] and lr.strip_provenance(body_in["body"]) == "reply"


# --- verification -----------------------------------------------------------------------------------------------

def _readback(title="B17 — A2A", comments=("root comment", "reply"), state_type="started", parent="new-54"):
    return {"title": title, "description": lr.PROVENANCE_PREFIX + " x\n\n", "priority": 3,
            "state": {"type": state_type}, "parent": {"id": parent} if parent else None,
            "comments": [{"body": lr.PROVENANCE_PREFIX + " y\n\n" + b, "createdAt": f"2026-09-27T00:00:0{n}Z"}
                         for n, b in enumerate(comments)]}


def test_verify_passes_on_a_faithful_readback(snap):
    assert lr.verify(CHILD, _readback(), lr.VerifyContext(snap, {"i-54": "new-54"}, TARGET_STATES)) == []


def test_verify_names_each_mismatch(snap):
    bad = lr.verify(CHILD, _readback(title="wrong", comments=("root comment",), state_type="backlog", parent=None),
                    lr.VerifyContext(snap, {"i-54": "new-54"}, TARGET_STATES))
    joined = " | ".join(bad)
    assert "title" in joined and "comments" in joined and "state" in joined and "parent" in joined


# --- findings from the first live drill (2026-09-27) -------------------------------------------------------------

def test_mentions_are_neutralized_so_a_restore_does_not_reinvoke_agents(snap):
    # The first live drill restored EMA-240's comments verbatim; their `@SpecBot` mentions re-invoked the agent
    # (43 comments read back vs 15 restored) and spent its capped monthly analyses.
    cm = dict(COMMENTS[1], body="please check @SpecBot and @emangini")
    body = lr.build_comment_input(cm, "new-13", {}, snap)["body"]
    assert "@SpecBot" not in body and "@emangini" not in body
    assert lr._norm(lr.strip_provenance(body)) == "please check @SpecBot and @emangini"   # still compares equal


def test_norm_treats_linear_markdown_escapes_as_equal():
    # Linear stores `*.fastmcp.app` as `\\*.fastmcp.app` (observed on EMA-13's description).
    assert lr._norm("servers on *.fastmcp.app") == lr._norm("servers on \\*.fastmcp.app")


def test_verify_ignores_comments_written_by_bots(snap):
    rb = _readback()
    rb["comments"].append({"body": "## NOT READY — 40/100", "createdAt": "2026-09-27T00:00:09Z",
                           "botActor": {"name": "SpecBot"}})
    assert lr.verify(CHILD, rb, lr.VerifyContext(snap, {"i-54": "new-54"}, TARGET_STATES)) == []


def test_bot_authored_comments_are_attributed_to_the_bot(snap):
    cm = dict(COMMENTS[1], user=None, botActor={"name": "SpecBot"})
    assert "originally by SpecBot" in lr.build_comment_input(cm, "n", {}, snap)["body"]


# --- the drill --------------------------------------------------------------------------------------------------

class FakeLinear:
    """Minimal fake of the mutations/queries the drill uses; records every call."""

    def __init__(self, fail_verify=False):
        self.calls, self.issues, self.comments, self.fail_verify = [], {}, {}, fail_verify

    def __call__(self, query, variables=None):
        v = variables or {}
        # Record the operation's root field (issueCreate, teamDelete, …) — the word after the first "{".
        self.calls.append(re.search(r"\{\s*(\w+)", query).group(1))
        if "teamCreate" in query:
            return {"teamCreate": {"success": True, "team": {"id": "t-new", "key": v["i"]["key"],
                                                              "states": {"nodes": TARGET_STATES}}}}
        if "issueCreate" in query:
            nid = f"new-{len(self.issues) + 1}"
            self.issues[nid] = dict(v["i"])
            return {"issueCreate": {"success": True, "issue": {"id": nid, "identifier": f"RD-{len(self.issues)}"}}}
        if "commentCreate" in query:
            cid = f"cm-{len(self.comments) + 1}"
            self.comments[cid] = dict(v["i"])
            return {"commentCreate": {"success": True, "comment": {"id": cid}}}
        if "issueDelete" in query:
            return {"issueDelete": {"success": True}}
        if "teamDelete" in query:
            return {"teamDelete": {"success": True}}
        if "issue(id:" in query:
            src = self.issues[v["id"]]
            state = next(s for s in TARGET_STATES if s["id"] == src.get("stateId"))
            cms = [c for c in self.comments.values() if c["issueId"] == v["id"]]
            return {"issue": {"title": "tampered" if self.fail_verify else src["title"], "description": src["description"],
                              "priority": src["priority"], "state": {"type": state["type"]},
                              "parent": {"id": src["parentId"]} if src.get("parentId") else None,
                              "comments": {"nodes": [{"body": c["body"], "createdAt": f"2026-09-27T00:00:{n:02d}Z"}
                                                     for n, c in enumerate(cms)]}}}
        raise AssertionError(f"unexpected query {query[:60]}")


def test_drill_restores_verifies_and_tears_down(snap):
    fake = FakeLinear()
    report = lr.drill(fake, snap, ["EMA-13", "EMA-54"], lr.DrillOptions(TS, "RD"))
    assert report["mismatches"] == [] and report["restored"] == ["EMA-54", "EMA-13"]
    assert report["comments"] == 2
    assert fake.calls.count("issueDelete") == 2 and fake.calls[-1] == "teamDelete"   # everything removed, team last


def test_drill_tears_down_even_when_verification_fails(snap):
    fake = FakeLinear(fail_verify=True)
    report = lr.drill(fake, snap, ["EMA-54"], lr.DrillOptions(TS, "RD"))
    assert report["mismatches"] and "title" in report["mismatches"][0]
    assert "teamDelete" in fake.calls


def test_gql_errors_fail_closed_even_on_http_200(monkeypatch):
    class R:
        def __init__(self, body): self.body = body
        def read(self): return json.dumps(self.body).encode()
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setenv("LINEAR_API_KEY", "k")
    monkeypatch.setattr(lr.urllib.request, "urlopen", lambda req, timeout: R({"errors": [{"message": "usage limit"}]}))
    with pytest.raises(lr.RestoreError, match="usage limit"):
        lr.gql("{ x }")


def test_a_restore_error_mid_drill_still_tears_down_and_propagates(snap):
    # Ruff B012 caught the first version returning from `finally`, which would have swallowed this error.
    class Failing(FakeLinear):
        def __call__(self, query, variables=None):
            if "commentCreate" in query:
                self.calls.append("commentCreate")
                raise lr.RestoreError("usage limit exceeded")
            return super().__call__(query, variables)
    fake = Failing()
    with pytest.raises(lr.RestoreError, match="usage limit"):
        lr.drill(fake, snap, ["EMA-13", "EMA-54"], lr.DrillOptions(TS, "RD"))
    assert "issueDelete" in fake.calls and fake.calls[-1] == "teamDelete"
