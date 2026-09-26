"""Tests for the dagster-free ``linear_export`` leaf module (B194 — nightly Linear workspace backup).

Loaded in isolation via the ``linear_export`` fixture, so the fast lane never imports dagster. The module takes an
injected ``post(query, variables) -> response_json`` so every test drives it with a fake transport and NO network or
key. The response shapes below were CAPTURED from the live Linear GraphQL API on 2026-09-26 with the read-only key
(an auth failure, an argument-validation error returned with HTTP 200, paginated connections, nested issue history)
— the fakes encode observed behaviour, not assumed behaviour.
"""
import datetime

import pytest

# --- captured Linear payloads (verbatim shapes, values abbreviated) -------------------------------------------

AUTH_ERROR = {"errors": [{
    "message": "Authentication required, not authenticated",
    "extensions": {"type": "authentication error", "code": "AUTHENTICATION_ERROR", "statusCode": 401,
                   "userError": True, "http": {"status": 401}},
}]}

# Linear answers a bad argument with HTTP 200 and an `errors` array — a transport that only checks the status
# code would read this as success. Captured from `issues(after:"bogus-cursor")`.
VALIDATION_ERROR_200 = {"errors": [{
    "message": "Argument Validation Error", "path": ["issues"],
    "extensions": {"code": "INVALID_INPUT"},
}]}

# __type introspection shape (trimmed to the field kinds the selection builder must handle).
ISSUE_TYPE = {"data": {"__type": {"name": "Issue", "kind": "OBJECT", "fields": [
    {"name": "id", "args": [], "type": {"kind": "NON_NULL", "name": None, "ofType": {"kind": "SCALAR", "name": "ID", "ofType": None}}},
    {"name": "title", "args": [], "type": {"kind": "NON_NULL", "name": None, "ofType": {"kind": "SCALAR", "name": "String", "ofType": None}}},
    {"name": "slaType", "args": [], "type": {"kind": "ENUM", "name": "SLADayCountType", "ofType": None}},
    {"name": "labelIds", "args": [], "type": {"kind": "NON_NULL", "name": None, "ofType": {"kind": "LIST", "name": None, "ofType": {"kind": "NON_NULL", "name": None, "ofType": {"kind": "SCALAR", "name": "String"}}}}},
    {"name": "team", "args": [], "type": {"kind": "NON_NULL", "name": None, "ofType": {"kind": "OBJECT", "name": "Team", "ofType": None}}},
    {"name": "parent", "args": [], "type": {"kind": "OBJECT", "name": "Issue", "ofType": None}},
    {"name": "reactions", "args": [], "type": {"kind": "NON_NULL", "name": None, "ofType": {"kind": "LIST", "name": None, "ofType": {"kind": "NON_NULL", "name": None, "ofType": {"kind": "OBJECT", "name": "Reaction"}}}}},
    {"name": "history", "args": [{"name": "first", "type": {"kind": "SCALAR"}}], "type": {"kind": "NON_NULL", "name": None, "ofType": {"kind": "OBJECT", "name": "IssueHistoryConnection", "ofType": None}}},
    {"name": "botActor", "args": [], "type": {"kind": "OBJECT", "name": "ActorBot", "ofType": None}},
    {"name": "descriptionState", "args": [{"name": "format", "type": {"kind": "NON_NULL"}}], "type": {"kind": "SCALAR", "name": "String", "ofType": None}},
]}}}
TYPES_WITH_ID = {"Team", "Issue", "Reaction"}   # ActorBot has no `id` field in the real schema


def _page(root, nodes, next_cursor=None):
    return {"data": {root: {"pageInfo": {"hasNextPage": next_cursor is not None, "endCursor": next_cursor},
                            "nodes": nodes}}}


class FakePost:
    """Replays queued responses and records every (query, variables) it was called with."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, query, variables=None):
        self.calls.append((query, variables or {}))
        if not self.responses:
            raise AssertionError(f"unexpected extra call: {query[:80]}")
        return self.responses.pop(0)


# --- selection building --------------------------------------------------------------------------------------

def test_selection_keeps_scalars_enums_and_scalar_lists(linear_export):
    sel = linear_export.selection_from_type(ISSUE_TYPE["data"]["__type"], TYPES_WITH_ID.__contains__)
    for field in ("id", "title", "slaType", "labelIds"):
        assert field in sel.split(), f"{field} missing from {sel!r}"


def test_selection_references_single_objects_by_id_only(linear_export):
    sel = linear_export.selection_from_type(ISSUE_TYPE["data"]["__type"], TYPES_WITH_ID.__contains__)
    assert "team { id }" in sel and "parent { id }" in sel


def test_selection_skips_lists_of_objects_connections_required_args_and_idless_objects(linear_export):
    sel = linear_export.selection_from_type(ISSUE_TYPE["data"]["__type"], TYPES_WITH_ID.__contains__)
    assert "reactions" not in sel          # list of objects: not a reference, and expensive
    assert "history" not in sel            # connections are fetched explicitly, never implicitly
    assert "descriptionState" not in sel   # a required argument cannot be supplied generically
    assert "botActor" not in sel           # no `id` to reference it by


# --- pagination ----------------------------------------------------------------------------------------------

def test_paginate_follows_cursors_and_concatenates_nodes(linear_export):
    post = FakePost(_page("issues", [{"id": "a"}, {"id": "b"}], "c1"), _page("issues", [{"id": "c"}]))
    nodes = linear_export.paginate(post, "issues", "id", first=2)
    assert [n["id"] for n in nodes] == ["a", "b", "c"]
    assert post.calls[0][1].get("after") is None and post.calls[1][1]["after"] == "c1"
    assert "includeArchived: true" in post.calls[0][0]   # archived items are part of the backup


def test_paginate_fails_closed_on_errors_inside_a_200_response(linear_export):
    post = FakePost(VALIDATION_ERROR_200)
    with pytest.raises(linear_export.LinearExportError, match="issues.*Argument Validation Error"):
        linear_export.paginate(post, "issues", "id")


def test_paginate_raises_a_distinct_auth_error(linear_export):
    post = FakePost(AUTH_ERROR)
    with pytest.raises(linear_export.LinearAuthError, match="Authentication required"):
        linear_export.paginate(post, "issues", "id")


def test_paginate_fails_closed_when_the_root_is_missing(linear_export):
    post = FakePost({"data": {}})
    with pytest.raises(linear_export.LinearExportError, match="no 'issues' in the response"):
        linear_export.paginate(post, "issues", "id")


def test_paginate_refuses_a_cursor_that_does_not_advance(linear_export):
    post = FakePost(_page("issues", [{"id": "a"}], "same"), _page("issues", [{"id": "b"}], "same"))
    with pytest.raises(linear_export.LinearExportError, match="cursor did not advance"):
        linear_export.paginate(post, "issues", "id")


# --- nested issue history ------------------------------------------------------------------------------------

def test_complete_history_pages_only_the_issues_that_have_more(linear_export):
    issues = [
        {"id": "i1", "history": {"pageInfo": {"hasNextPage": False, "endCursor": "h1"}, "nodes": [{"id": "e1"}]}},
        {"id": "i2", "history": {"pageInfo": {"hasNextPage": True, "endCursor": "h2"}, "nodes": [{"id": "e2"}]}},
    ]
    post = FakePost({"data": {"issue": {"history": {"pageInfo": {"hasNextPage": False, "endCursor": "h3"},
                                                    "nodes": [{"id": "e3"}]}}}})
    fetched = linear_export.complete_history(post, issues, "id")
    assert fetched == 1
    assert [e["id"] for e in issues[1]["history"]["nodes"]] == ["e2", "e3"]
    assert issues[1]["history"]["pageInfo"]["hasNextPage"] is False
    assert post.calls[0][1] == {"id": "i2", "after": "h2"}


# --- validation + manifest -----------------------------------------------------------------------------------

def _full_snapshot():
    snap = {entity: [{"id": f"{entity}-1"}] for entity in linear_export_required()}
    snap["issues"] = [{"id": "i1", "history": {"pageInfo": {"hasNextPage": False}, "nodes": [{"id": "e1"}, {"id": "e2"}]}}]
    snap["projectUpdates"] = []   # optional: legitimately empty before the first update is posted
    return snap


def linear_export_required():
    # Mirrors REQUIRED_NONEMPTY in the module; asserted equal below so the two cannot drift silently.
    return ("issues", "comments", "projects", "initiatives", "issueLabels", "templates", "customViews",
            "workflowStates", "teams", "users")


def test_required_entities_match_the_module(linear_export):
    assert tuple(linear_export.REQUIRED_NONEMPTY) == linear_export_required()


def test_validate_rejects_an_empty_required_entity(linear_export):
    snap = _full_snapshot()
    snap["comments"] = []
    with pytest.raises(linear_export.LinearExportError, match="comments"):
        linear_export.validate(snap)


def test_validate_rejects_a_snapshot_with_no_issue_history(linear_export):
    snap = _full_snapshot()
    snap["issues"][0]["history"]["nodes"] = []
    with pytest.raises(linear_export.LinearExportError, match="history"):
        linear_export.validate(snap)


def test_validate_accepts_a_complete_snapshot_with_empty_optional_entities(linear_export):
    linear_export.validate(_full_snapshot())


def test_manifest_counts_every_entity_and_the_nested_history(linear_export):
    started = datetime.datetime(2026, 9, 27, 9, 20, 0, tzinfo=datetime.timezone.utc)
    finished = started + datetime.timedelta(seconds=42)
    m = linear_export.build_manifest(_full_snapshot(), started, finished)
    assert m["counts"]["issues"] == 1 and m["counts"]["projectUpdates"] == 0
    assert m["counts"]["issueHistory"] == 2
    assert m["started_at"] == "2026-09-27T09:20:00+00:00" and m["duration_s"] == 42.0
    assert m["format_version"] == linear_export.FORMAT_VERSION


def test_snapshot_prefix_is_utc_and_sortable(linear_export):
    ts = datetime.datetime(2026, 9, 27, 5, 20, 7, tzinfo=datetime.timezone(datetime.timedelta(hours=-4)))
    assert linear_export.snapshot_prefix(ts) == "snapshots/2026-09-27T092007Z/"


def test_snapshot_prefix_refuses_a_naive_timestamp(linear_export):
    with pytest.raises(ValueError, match="timezone"):
        linear_export.snapshot_prefix(datetime.datetime(2026, 9, 27, 9, 20))
