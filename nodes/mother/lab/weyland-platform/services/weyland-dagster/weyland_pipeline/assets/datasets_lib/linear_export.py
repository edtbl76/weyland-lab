"""Linear workspace export — the dagster-free core of the B194 nightly backup.

Pages every Linear entity worth restoring out of the GraphQL API into plain dicts, validates the result, and
describes it in a manifest. The dagster asset (``assets/linear_backup.py``) owns the transport, the key and the
MinIO write; this module owns the decisions, so the fast test lane can exercise all of them with a fake transport.

Stdlib only, absolute imports only: ``conftest.load_isolated`` loads it without dagster (see ``.importlinter``).

Shapes observed against the live API (2026-09-26, read-only key) that the logic depends on:
  * A request error can arrive with HTTP **200** and an ``errors`` array (e.g. a bad cursor). Any ``errors`` fails.
  * A bad or missing key is HTTP 401 with ``extensions.code == "AUTHENTICATION_ERROR"``.
  * Linear caps ONE query at 10,000 complexity. A 50-issue page with 50 history events each costs ~900.
  * Full-schema introspection exceeds that cap, so selections are built one type at a time (``__type``).
"""
import datetime

FORMAT_VERSION = 1

# (root connection, node type). Order is the order of the snapshot files; issues first because it is the largest.
ENTITIES = (
    ("issues", "Issue"),
    ("comments", "Comment"),
    ("issueRelations", "IssueRelation"),
    ("attachments", "Attachment"),
    ("projects", "Project"),
    ("projectUpdates", "ProjectUpdate"),
    ("projectMilestones", "ProjectMilestone"),
    ("projectStatuses", "ProjectStatus"),
    ("initiatives", "Initiative"),
    ("initiativeUpdates", "InitiativeUpdate"),
    ("initiativeToProjects", "InitiativeToProject"),
    ("issueLabels", "IssueLabel"),
    ("projectLabels", "ProjectLabel"),
    ("initiativeLabels", "InitiativeLabel"),
    ("customViews", "CustomView"),
    ("cycles", "Cycle"),
    ("documents", "Document"),
    ("teams", "Team"),
    ("users", "User"),
    ("workflowStates", "WorkflowState"),
)

# Entities a healthy workspace can never have zero of. An empty one means the export silently lost it (a scope
# change on the key, an API change) — which must fail the run, never publish as a complete backup. Everything else
# (project/initiative updates, the extra label kinds) may legitimately be empty.
REQUIRED_NONEMPTY = ("issues", "comments", "projects", "initiatives", "issueLabels", "templates", "customViews",
                     "workflowStates", "teams", "users")

PAGE_SIZE = 50
HISTORY_PAGE_SIZE = 50
# `templates` is a plain list, not a connection; `templateData` carries the template body.
TEMPLATES_QUERY = "{ templates { id name type description createdAt updatedAt archivedAt team { id } templateData } }"

TYPE_QUERY = (
    "query($n: String!) { __type(name: $n) { name kind fields { name args { name type { kind } } "
    "type { kind name ofType { kind name ofType { kind name ofType { kind name } } } } } } }"
)


class LinearExportError(RuntimeError):
    """The export cannot be trusted as complete. Never write a snapshot after this."""


class LinearAuthError(LinearExportError):
    """The key was rejected (revoked, expired, or missing). Distinct so the alert says what to fix."""


def _base(t):
    while t.get("ofType"):
        t = t["ofType"]
    return t


def _is_list(t):
    if t["kind"] == "NON_NULL":
        t = t["ofType"]
    return t["kind"] == "LIST"


def _needs_args(field):
    return any(a["type"]["kind"] == "NON_NULL" for a in field.get("args") or [])


def _is_single_ref(field, base, has_id):
    """A single related object (not a list, not a connection) that can be referenced by its id."""
    if base["kind"] != "OBJECT" or _is_list(field["type"]) or base["name"].endswith("Connection"):
        return False
    return has_id(base["name"])


def _field_selection(field, has_id):
    """The selection for one field, or None to skip it."""
    if _needs_args(field):
        return None
    base = _base(field["type"])
    if base["kind"] in ("SCALAR", "ENUM"):
        return field["name"]
    if _is_single_ref(field, base, has_id):
        return f"{field['name']} {{ id }}"
    return None


def selection_from_type(type_json, has_id):
    """Build a GraphQL selection for one node type: every argument-free scalar/enum field (scalar lists included)
    plus ``field { id }`` for each single-object reference whose type has an ``id``. Connections and lists of
    objects are skipped on purpose — they are fetched explicitly (issue history) or live in their own root
    connection (comments, relations, attachments), which keeps every page's complexity predictable."""
    parts = (_field_selection(f, has_id) for f in type_json.get("fields") or [])
    return " ".join(p for p in parts if p)


def _raise_for_errors(errors, what):
    codes = {(e.get("extensions") or {}).get("code") for e in errors}
    msg = "; ".join(str(e.get("message")) for e in errors)
    if "AUTHENTICATION_ERROR" in codes:
        raise LinearAuthError(f"{what}: {msg}")
    raise LinearExportError(f"{what}: {msg}")


def check_response(resp, what):
    """Raise unless ``resp`` is an error-free GraphQL response. Linear reports some failures with HTTP 200."""
    if not isinstance(resp, dict):
        raise LinearExportError(f"{what}: non-JSON-object response: {resp!r:.200}")
    if resp.get("errors"):
        _raise_for_errors(resp["errors"], what)
    if not isinstance(resp.get("data"), dict):
        raise LinearExportError(f"{what}: response has no data object")
    return resp["data"]


def _next_cursor(info, what, seen):
    """The cursor for the next page, or None when this was the last page. Refuses a cursor that repeats."""
    if not info.get("hasNextPage"):
        return None
    after = info.get("endCursor")
    if not after or after in seen:
        raise LinearExportError(f"{what}: cursor did not advance ({after!r}) — refusing to loop")
    seen.add(after)
    return after


def paginate(post, root, selection, first=PAGE_SIZE):
    """Every node of root connection ``root`` (archived included), following cursors to the end. ``selection`` is the
    node selection, including any nested connection the caller wants (issue history)."""
    query = (f"query($after: String) {{ {root}(first: {first}, after: $after, includeArchived: true) "
             f"{{ pageInfo {{ hasNextPage endCursor }} nodes {{ {selection} }} }} }}")
    nodes, after, seen = [], None, set()
    while True:
        conn = check_response(post(query, {"after": after}), root).get(root)
        if not isinstance(conn, dict):
            raise LinearExportError(f"no '{root}' in the response")
        nodes.extend(conn.get("nodes") or [])
        after = _next_cursor(conn.get("pageInfo") or {}, root, seen)
        if after is None:
            return nodes


def _history_query(history_selection, first):
    return (f"query($id: String!, $after: String) {{ issue(id: $id) {{ history(first: {first}, after: $after) "
            f"{{ pageInfo {{ hasNextPage endCursor }} nodes {{ {history_selection} }} }} }} }}")


def _finish_issue_history(post, query, issue):
    """Page one issue's history to the end, appending to its first page in place. Returns pages fetched."""
    hist = issue.get("history") or {}
    what = f"issue {issue.get('id')} history"
    seen, fetched = set(), 0
    after = _next_cursor(hist.get("pageInfo") or {}, what, seen)
    while after is not None:
        data = check_response(post(query, {"id": issue["id"], "after": after}), what)
        page = ((data.get("issue") or {}).get("history")) or {}
        if not isinstance(page.get("nodes"), list):
            raise LinearExportError(f"{what}: page missing nodes")
        hist.setdefault("nodes", []).extend(page["nodes"])
        hist["pageInfo"] = page.get("pageInfo") or {}
        fetched += 1
        after = _next_cursor(hist["pageInfo"], what, seen)
    return fetched


def complete_history(post, issues, history_selection, first=HISTORY_PAGE_SIZE):
    """Page the rest of each issue's history where the nested first page was not the whole of it.
    Returns how many extra pages were fetched."""
    query = _history_query(history_selection, first)
    return sum(_finish_issue_history(post, query, issue) for issue in issues)


def history_count(snapshot):
    return sum(len(((i.get("history") or {}).get("nodes")) or []) for i in snapshot.get("issues") or [])


def validate(snapshot):
    """Refuse a snapshot that is missing something a real workspace always has."""
    empty = [e for e in REQUIRED_NONEMPTY if not snapshot.get(e)]
    if empty:
        raise LinearExportError(f"required entities came back empty: {', '.join(empty)}")
    if history_count(snapshot) == 0:
        raise LinearExportError("issues exported with no history at all — state history was not captured")


def build_manifest(snapshot, started, finished):
    counts = {entity: len(nodes) for entity, nodes in snapshot.items()}
    counts["issueHistory"] = history_count(snapshot)
    return {
        "format_version": FORMAT_VERSION,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_s": round((finished - started).total_seconds(), 3),
        "counts": counts,
    }


def snapshot_prefix(ts):
    """``snapshots/<UTC timestamp>/`` — sorts lexically in time order. A naive timestamp is ambiguous, so refuse it."""
    if ts.tzinfo is None:
        raise ValueError("snapshot timestamp must carry a timezone")
    return ts.astimezone(datetime.timezone.utc).strftime("snapshots/%Y-%m-%dT%H%M%SZ/")


class _Schema:
    """Per-type introspection, cached — full-schema introspection exceeds Linear's complexity cap."""

    def __init__(self, post):
        self.post = post
        self.types = {}

    def get(self, name):
        if name not in self.types:
            data = check_response(self.post(TYPE_QUERY, {"n": name}), f"introspect {name}")
            self.types[name] = data.get("__type")
        return self.types[name]

    def has_id(self, name):
        t = self.get(name)
        return bool(t) and any(f["name"] == "id" for f in t.get("fields") or [])

    def selection(self, name):
        t = self.get(name)
        if not t:
            raise LinearExportError(f"type {name} not found in the schema")
        sel = selection_from_type(t, self.has_id)
        if "id" not in sel.split():
            raise LinearExportError(f"type {name}: generated selection has no id field")
        return sel


def _issue_history_extra(history_sel):
    return (f"history(first: {HISTORY_PAGE_SIZE}) {{ pageInfo {{ hasNextPage endCursor }} "
            f"nodes {{ {history_sel} }} }}")


def export_workspace(post, log=print):
    """The whole export: introspect each node type, page every entity, finish issue history, fetch templates,
    validate. Returns the snapshot dict (entity -> list of nodes). Raises LinearExportError on anything partial."""
    schema = _Schema(post)
    history_sel = schema.selection("IssueHistory")
    snapshot = {}
    for root, node_type in ENTITIES:
        selection = schema.selection(node_type)
        if root == "issues":
            selection = f"{selection} {_issue_history_extra(history_sel)}"
        snapshot[root] = paginate(post, root, selection)
        log(f"linear export: {root} = {len(snapshot[root])}")
    extra_pages = complete_history(post, snapshot["issues"], history_sel)
    log(f"linear export: issue history = {history_count(snapshot)} events ({extra_pages} extra pages)")
    snapshot["templates"] = check_response(post(TEMPLATES_QUERY, {}), "templates").get("templates") or []
    log(f"linear export: templates = {len(snapshot['templates'])}")
    validate(snapshot)
    return snapshot
