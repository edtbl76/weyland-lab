"""Tests for linear-high-project-views.py — builds + verifies the Linear "High · <project>" view set (B119).

The script shipped on 2026-09-25 with no tests and dropped `scripts/` coverage 69% -> 65%, which failed every CI
pipeline's test-python step (the coverage ratchet) and so blocked every image ship. These cover the decisions it makes:
fail-closed transport (GraphQL errors, HTTP errors, success:false, zero projects), create-vs-skip idempotency, the
grouping preference applied only once, and the exit code that says whether every view matched an independent count.
The transport is replaced by a fake keyed on the query text, so no network or key is needed.
"""
import importlib.util
import io
import json
import os
import urllib.error

import pytest

_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "linear-high-project-views.py")


@pytest.fixture
def views(monkeypatch):
    monkeypatch.setenv("LINEAR_API_KEY", "test-key")
    spec = importlib.util.spec_from_file_location("linear_high_project_views", _PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeLinear:
    """Answers the script's queries from in-memory state and records mutations."""

    def __init__(self, projects, existing_views=None, issues=None, grouped=False, view_counts=None):
        self.projects = projects
        self.views = dict(existing_views or {})
        self.issues = issues or []          # list of project ids (None = no project), one per open High issue
        self.grouped = grouped
        self.view_counts = view_counts      # optional override {view_id: count}
        self.created, self.prefs = [], 0
        self.filters = {}

    def __call__(self, query, variables=None):
        v = variables or {}
        if "projects(first:50)" in query:
            return {"projects": {"nodes": self.projects}}
        if "customViews(first:100)" in query:
            return {"customViews": {"nodes": [{"id": i, "name": n} for n, i in self.views.items()]}}
        if "customViewCreate" in query:
            name = v["i"]["name"]
            vid = f"view-{len(self.views) + 1}"
            self.views[name] = vid
            self.filters[vid] = v["i"]["filterData"]
            self.created.append(name)
            return {"customViewCreate": {"success": True, "customView": {"id": vid, "name": name}}}
        if "viewPreferencesCreate" in query:
            self.prefs += 1
            self.grouped = True
            return {"viewPreferencesCreate": {"success": True}}
        if "issueGrouping" in query:
            return {"customView": {"viewPreferencesValues": {"issueGrouping": "project" if self.grouped else None}}}
        if "customView(id:$id){ issues" in query:
            return {"customView": {"issues": {"nodes": [{"id": "x"}] * self._count(v["id"])}}}
        if "issues(first:250" in query:
            return {"issues": {"nodes": [{"project": ({"id": p} if p else None)} for p in self.issues]}}
        raise AssertionError(f"unexpected query: {query[:80]}")

    def _count(self, view_id):
        if self.view_counts and view_id in self.view_counts:
            return self.view_counts[view_id]
        flt = self.filters.get(view_id, {})
        pid = ((flt.get("project") or {}).get("id") or {}).get("eq")
        return len(self.issues) if pid is None else sum(1 for p in self.issues if p == pid)


LIVE = [{"id": "p1", "name": "Weyland Lab", "status": {"type": "started"}},
        {"id": "p2", "name": "algopedia", "status": {"type": "backlog"}},
        {"id": "p3", "name": "Old Thing", "status": {"type": "completed"}}]


# --- transport ------------------------------------------------------------------------------------------------

def _resp(body):
    return io.BytesIO(json.dumps(body).encode())


def test_gql_returns_data_on_success(views, monkeypatch):
    monkeypatch.setattr(views.urllib.request, "urlopen", lambda req, timeout: _resp({"data": {"ok": 1}}))
    assert views.gql("{ ok }") == {"ok": 1}


def test_gql_exits_on_graphql_errors_even_with_http_200(views, monkeypatch):
    monkeypatch.setattr(views.urllib.request, "urlopen",
                        lambda req, timeout: _resp({"errors": [{"message": "Argument Validation Error"}]}))
    with pytest.raises(SystemExit, match="GraphQL error: .*Argument Validation Error"):
        views.gql("{ bad }")


def test_gql_exits_on_http_error_with_the_status(views, monkeypatch):
    def boom(req, timeout):
        raise urllib.error.HTTPError(views.API, 401, "Unauthorized", {}, io.BytesIO(b'{"errors":["auth"]}'))
    monkeypatch.setattr(views.urllib.request, "urlopen", boom)
    with pytest.raises(SystemExit, match="HTTP 401"):
        views.gql("{ viewer { id } }")


# --- ensure ---------------------------------------------------------------------------------------------------

def test_ensure_skips_an_existing_view_without_a_mutation(views, monkeypatch):
    fake = FakeLinear(LIVE)
    monkeypatch.setattr(views, "gql", fake)
    assert views.ensure({"High · X": "v9"}, "High · X", "d", {}) == "v9"
    assert fake.created == []


def test_ensure_exits_when_linear_reports_success_false(views, monkeypatch):
    monkeypatch.setattr(views, "gql", lambda q, v=None: {"customViewCreate": {"success": False, "customView": None}})
    with pytest.raises(SystemExit, match="success=false creating High · X"):
        views.ensure({}, "High · X", "d", {})


# --- main -----------------------------------------------------------------------------------------------------

def test_main_refuses_when_no_live_projects(views, monkeypatch):
    monkeypatch.setattr(views, "gql", FakeLinear([{"id": "p3", "name": "Old", "status": {"type": "canceled"}}]))
    with pytest.raises(SystemExit, match="no live projects"):
        views.main()


def test_main_builds_one_view_per_live_project_plus_the_index_and_exits_0(views, monkeypatch):
    fake = FakeLinear(LIVE, issues=["p1", "p1", "p2", None])
    monkeypatch.setattr(views, "gql", fake)
    with pytest.raises(SystemExit) as exc:
        views.main()
    assert exc.value.code == 0
    assert fake.created == ["High · algopedia", "High · Weyland Lab", "High — all projects"]   # case-insensitive sort
    assert "High · Old Thing" not in fake.views                                              # completed project skipped
    assert fake.prefs == 1                                                                   # grouping applied once


def test_main_is_idempotent_and_does_not_restack_grouping(views, monkeypatch):
    existing = {"High · Weyland Lab": "a", "High · algopedia": "b", "High — all projects": "c"}
    fake = FakeLinear(LIVE, existing_views=existing, issues=["p1"], grouped=True,
                      view_counts={"a": 1, "b": 0, "c": 1})
    monkeypatch.setattr(views, "gql", fake)
    with pytest.raises(SystemExit) as exc:
        views.main()
    assert exc.value.code == 0
    assert fake.created == [] and fake.prefs == 0


def test_main_exits_1_when_a_view_count_disagrees_with_the_independent_query(views, monkeypatch):
    existing = {"High · Weyland Lab": "a", "High · algopedia": "b", "High — all projects": "c"}
    fake = FakeLinear(LIVE, existing_views=existing, issues=["p1", "p1"], grouped=True,
                      view_counts={"a": 1, "b": 0, "c": 2})   # view a shows 1, independent says 2
    monkeypatch.setattr(views, "gql", fake)
    with pytest.raises(SystemExit) as exc:
        views.main()
    assert exc.value.code == 1
