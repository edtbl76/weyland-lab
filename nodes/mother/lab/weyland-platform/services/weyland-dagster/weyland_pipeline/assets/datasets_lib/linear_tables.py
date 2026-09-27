"""Linear snapshot -> typed Arrow tables for the lakehouse (B194 Slice 3). Dagster-free; pyarrow only.

The nightly B194 snapshot (raw JSON, one file per entity) is the backup; this flattens its CURRENT state into tables
in the Iceberg namespace ``linear`` so dbt can model it: B185 cycle time, EMA-172 flow (the Linear side of DORA),
B119.1 initiative progress. Every table has an EXPLICIT schema — an all-null column would otherwise infer Arrow's
null type, which Iceberg rejects (and several columns ARE all-null today: estimates are unused, no initiative
updates exist yet). Timestamps stay ISO-8601 strings; dbt casts them (``from_iso8601_timestamp``).

Absolute imports only: ``conftest.load_isolated`` loads this without dagster (see ``.importlinter``).
"""
import pyarrow as pa

STR, INT, FLT = pa.string(), pa.int64(), pa.float64()


def _ref(node, key):
    return (node.get(key) or {}).get("id")


# table -> (snapshot entity, [(column, arrow type, extractor(node))]). `snapshot_at` is appended to every table.
TABLES = {
    "issues": ("issues", [
        ("id", STR, lambda n: n["id"]),
        ("identifier", STR, lambda n: n.get("identifier")),
        ("title", STR, lambda n: n.get("title")),
        ("team_id", STR, lambda n: _ref(n, "team")),
        ("project_id", STR, lambda n: _ref(n, "project")),
        ("parent_id", STR, lambda n: _ref(n, "parent")),
        ("state_id", STR, lambda n: _ref(n, "state")),
        ("priority", INT, lambda n: n.get("priority")),
        ("estimate", FLT, lambda n: n.get("estimate")),
        ("label_ids", STR, lambda n: ",".join(n.get("labelIds") or [])),
        ("created_at", STR, lambda n: n.get("createdAt")),
        ("started_at", STR, lambda n: n.get("startedAt")),
        ("completed_at", STR, lambda n: n.get("completedAt")),
        ("canceled_at", STR, lambda n: n.get("canceledAt")),
        ("archived_at", STR, lambda n: n.get("archivedAt")),
    ]),
    "workflow_states": ("workflowStates", [
        ("id", STR, lambda n: n["id"]),
        ("name", STR, lambda n: n.get("name")),
        ("type", STR, lambda n: n.get("type")),
        ("team_id", STR, lambda n: _ref(n, "team")),
    ]),
    "issue_labels": ("issueLabels", [
        ("id", STR, lambda n: n["id"]),
        ("name", STR, lambda n: n.get("name")),
        ("parent_id", STR, lambda n: _ref(n, "parent")),
        ("team_id", STR, lambda n: _ref(n, "team")),
    ]),
    "projects": ("projects", [
        ("id", STR, lambda n: n["id"]),
        ("name", STR, lambda n: n.get("name")),
        ("status_id", STR, lambda n: _ref(n, "status")),
        ("progress", FLT, lambda n: n.get("progress")),
        ("lead_team_id", STR, lambda n: _ref(n, "leadTeam")),
        ("health", STR, lambda n: n.get("health")),
        ("created_at", STR, lambda n: n.get("createdAt")),
        ("started_at", STR, lambda n: n.get("startedAt")),
        ("completed_at", STR, lambda n: n.get("completedAt")),
        ("canceled_at", STR, lambda n: n.get("canceledAt")),
        ("target_date", STR, lambda n: n.get("targetDate")),
    ]),
    "initiatives": ("initiatives", [
        ("id", STR, lambda n: n["id"]),
        ("name", STR, lambda n: n.get("name")),
        ("status", STR, lambda n: n.get("status")),
        ("health", STR, lambda n: n.get("health")),
        ("target_date", STR, lambda n: n.get("targetDate")),
        ("owner_id", STR, lambda n: _ref(n, "owner")),
        ("created_at", STR, lambda n: n.get("createdAt")),
        ("completed_at", STR, lambda n: n.get("completedAt")),
    ]),
    "initiative_projects": ("initiativeToProjects", [
        ("initiative_id", STR, lambda n: _ref(n, "initiative")),
        ("project_id", STR, lambda n: _ref(n, "project")),
    ]),
    "initiative_updates": ("initiativeUpdates", [
        ("id", STR, lambda n: n["id"]),
        ("initiative_id", STR, lambda n: _ref(n, "initiative")),
        ("health", STR, lambda n: n.get("health")),
        ("body", STR, lambda n: n.get("body")),
        ("created_at", STR, lambda n: n.get("createdAt")),
    ]),
    "project_updates": ("projectUpdates", [
        ("id", STR, lambda n: n["id"]),
        ("project_id", STR, lambda n: _ref(n, "project")),
        ("health", STR, lambda n: n.get("health")),
        ("body", STR, lambda n: n.get("body")),
        ("created_at", STR, lambda n: n.get("createdAt")),
    ]),
}


STATE_CHANGE_COLUMNS = ("id", "issue_id", "created_at", "from_state_id", "to_state_id")


def schema(name):
    """The explicit Arrow schema of one lakehouse table (snapshot_at last)."""
    if name == "issue_state_changes":
        return pa.schema([pa.field(c, STR) for c in STATE_CHANGE_COLUMNS] + [pa.field("snapshot_at", STR)])
    return pa.schema([pa.field(col, typ) for col, typ, _ in TABLES[name][1]] + [pa.field("snapshot_at", STR)])


def _table(name, nodes, snapshot_at):
    cols = TABLES[name][1]
    data = {col: [fn(n) for n in nodes] for col, _, fn in cols}
    data["snapshot_at"] = [snapshot_at] * len(nodes)
    return pa.table(data, schema=schema(name))


def _state_changes(issues, snapshot_at):
    """Issue history reduced to state transitions (the input to cycle time); other history events are dropped."""
    rows = [{"id": e["id"], "issue_id": issue["id"], "created_at": e.get("createdAt"),
             "from_state_id": e.get("fromStateId"), "to_state_id": e.get("toStateId"), "snapshot_at": snapshot_at}
            for issue in issues for e in ((issue.get("history") or {}).get("nodes") or []) if e.get("toStateId")]
    return pa.Table.from_pylist(rows, schema=schema("issue_state_changes"))


def build_tables(snapshot, snapshot_at):
    """{table: pa.Table} for every lakehouse table. A MISSING entity raises: an absent issues list would publish as
    'no work', which is exactly the silent failure the snapshot's own validation exists to prevent."""
    missing = [entity for entity, _ in TABLES.values() if entity not in snapshot]
    if missing:
        raise ValueError(f"snapshot is missing entities: {', '.join(sorted(set(missing)))}")
    out = {name: _table(name, snapshot[entity], snapshot_at) for name, (entity, _) in TABLES.items()}
    out["issue_state_changes"] = _state_changes(snapshot["issues"], snapshot_at)
    return out


TABLES_ALL = tuple(TABLES) + ("issue_state_changes",)
