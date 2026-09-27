"""Tests for the dagster-free ``linear_tables`` leaf (B194 Slice 3 — the Linear lakehouse view).

It flattens a B194 snapshot into typed Arrow tables for Iceberg (namespace ``linear``), which dbt then models into the
B185 cycle-time, EMA-172 flow and B119.1 initiative-progress marts. What matters: every table has an EXPLICIT schema
(an all-null column would otherwise infer Arrow's null type, which Iceberg rejects), nested refs flatten to ids,
issue history keeps only state changes, and label ids survive as a joinable string. Node shapes are copied from a real
snapshot (2026-09-27).
"""
import pyarrow as pa
import pytest

AT = "2026-09-27T01:39:14+00:00"

SNAP = {
    "issues": [
        {"id": "i1", "identifier": "EMA-1", "title": "A", "team": {"id": "t"}, "project": {"id": "p1"},
         "parent": None, "state": {"id": "s-done"}, "priority": 2, "estimate": None, "labelIds": ["l1", "l2"],
         "createdAt": "2026-09-01T00:00:00.000Z", "startedAt": None, "completedAt": "2026-09-03T00:00:00.000Z",
         "canceledAt": None, "archivedAt": None,
         "history": {"nodes": [
             {"id": "h1", "createdAt": "2026-09-02T00:00:00.000Z", "fromStateId": "s-b", "toStateId": "s-done"},
             {"id": "h2", "createdAt": "2026-09-02T01:00:00.000Z", "fromStateId": None, "toStateId": None},
         ]}},
        {"id": "i2", "identifier": "EMA-2", "title": "B", "team": {"id": "t"}, "project": None,
         "parent": {"id": "i1"}, "state": {"id": "s-b"}, "priority": 0, "estimate": None, "labelIds": [],
         "createdAt": "2026-09-05T00:00:00.000Z", "startedAt": None, "completedAt": None,
         "canceledAt": None, "archivedAt": None, "history": {"nodes": []}},
    ],
    "workflowStates": [{"id": "s-done", "name": "Done", "type": "completed", "team": {"id": "t"}}],
    "issueLabels": [{"id": "l1", "name": "Spike", "parent": {"id": "g"}, "team": None}],
    "projects": [{"id": "p1", "name": "Weyland Lab", "status": {"id": "ps"}, "progress": 0.5, "leadTeam": {"id": "t"},
                  "health": None, "createdAt": "2026-08-01T00:00:00.000Z", "startedAt": None, "completedAt": None,
                  "canceledAt": None, "targetDate": None}],
    "initiatives": [{"id": "n1", "name": "Lab & Systems", "status": "Active", "health": None, "targetDate": None,
                     "owner": {"id": "u"}, "createdAt": "2026-09-24T00:00:00.000Z", "completedAt": None}],
    "initiativeToProjects": [{"id": "x", "initiative": {"id": "n1"}, "project": {"id": "p1"}}],
    "initiativeUpdates": [],
    "projectUpdates": [],
}


@pytest.fixture
def tables(linear_tables):
    return linear_tables.build_tables(SNAP, AT)


def test_every_declared_table_is_built_with_its_explicit_schema(linear_tables, tables):
    assert set(tables) == set(linear_tables.TABLES_ALL)
    for name, table in tables.items():
        assert table.schema == linear_tables.schema(name), name
        assert not any(pa.types.is_null(f.type) for f in table.schema), name   # Iceberg rejects null-typed columns


def test_an_empty_entity_still_yields_a_typed_empty_table(tables):
    assert tables["initiative_updates"].num_rows == 0
    assert tables["initiative_updates"].schema.field("health").type == pa.string()


def test_issue_rows_flatten_refs_and_join_label_ids(tables):
    rows = tables["issues"].to_pylist()
    first = next(r for r in rows if r["id"] == "i1")
    assert first["project_id"] == "p1" and first["state_id"] == "s-done" and first["parent_id"] is None
    assert first["label_ids"] == "l1,l2" and first["priority"] == 2 and first["snapshot_at"] == AT
    second = next(r for r in rows if r["id"] == "i2")
    assert second["project_id"] is None and second["parent_id"] == "i1" and second["label_ids"] == ""


def test_history_keeps_only_state_changes(tables):
    rows = tables["issue_state_changes"].to_pylist()
    assert [(r["id"], r["issue_id"], r["to_state_id"]) for r in rows] == [("h1", "i1", "s-done")]


def test_link_and_dimension_tables(tables):
    assert tables["initiative_projects"].to_pylist() == [{"initiative_id": "n1", "project_id": "p1", "snapshot_at": AT}]
    assert tables["issue_labels"].to_pylist()[0]["parent_id"] == "g"
    assert tables["projects"].to_pylist()[0]["progress"] == 0.5


def test_a_missing_entity_is_an_error_not_an_empty_table(linear_tables):
    # A snapshot without `issues` is broken; publishing an empty issues table would read as "no work".
    with pytest.raises(ValueError, match="issues"):
        linear_tables.build_tables({k: v for k, v in SNAP.items() if k != "issues"}, AT)
