"""Restore Linear issues + comments from a B194 snapshot, and run the DR drill (B194 Slice 2).

Usage (from rogueone; the WRITE-capable LINEAR_API_KEY comes from scripts/.env):
    set -a && . scripts/.env && set +a
    python3 scripts/linear_restore.py --snapshot <dir> --issues EMA-54,EMA-13 --drill      # scratch team, verify, delete
    python3 scripts/linear_restore.py --snapshot <dir> --issues EMA-54 --team-id <uuid>    # real restore, kept

<dir> is a downloaded snapshot directory (`mc cp -r weyland/linear-backup/snapshots/<ts>/ <dir>`). A directory with
no manifest.json is an incomplete snapshot and is refused.

What the Linear API can and cannot put back (recorded, never silently dropped):
  * RESTORED: title, description, priority, workflow state (by name, else by type), workspace labels, due date,
    parent/sub-issue links (when the parent is restored too), comments with their reply threading.
  * NOT RESTORABLE: the original identifier (EMA-n is reissued), the creator and comment authors (everything is
    created by the key's user), created/updated timestamps, the history log, reactions. The provenance header written
    at the top of each description and comment carries the originals so a reader can still see them.
  * DROPPED, and reported per issue: team-scoped labels (they belong to another team), cycle, project, milestone,
    assignee, estimate (not used in this workspace).

Exit codes: 0 = restored and every field verified (and, for --drill, torn down); 1 = a verification mismatch or a
teardown failure; 2 = could not run (bad snapshot, API error, missing key).
"""
import argparse
import dataclasses
import gzip
import json
import os
import re
import sys
import urllib.error
import urllib.request

API = "https://api.linear.app/graphql"
PROVENANCE_PREFIX = "> **Restored from backup**"
WORD_JOINER = "\u2060"
DROPPABLE = (("cycle", "cycle"), ("project", "project"), ("projectMilestone", "milestone"), ("assignee", "assignee"))


class RestoreError(RuntimeError):
    """The restore cannot proceed or its result cannot be trusted."""


# --- transport ------------------------------------------------------------------------------------------------

def _post_json(query, variables, key):
    req = urllib.request.Request(API, data=json.dumps({"query": query, "variables": variables or {}}).encode(),
                                 headers={"Authorization": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310  # nosec B310 — fixed https API URL
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return json.loads(exc.read() or b"{}")


def gql(query, variables=None):
    """One GraphQL call with the write key. Any `errors` fails, including those Linear returns with HTTP 200."""
    key = os.environ.get("LINEAR_API_KEY")
    if not key:
        raise RestoreError("LINEAR_API_KEY is not set (source scripts/.env)")
    body = _post_json(query, variables, key)
    if body.get("errors"):
        raise RestoreError("; ".join(str(e.get("message")) for e in body["errors"]))
    if not isinstance(body.get("data"), dict):
        raise RestoreError("response has no data object")
    return body["data"]


# --- snapshot ---------------------------------------------------------------------------------------------------

def load_snapshot(directory):
    """entity -> nodes, plus `_manifest`. Refuses a directory without manifest.json (the completeness marker)."""
    manifest_path = os.path.join(directory, "manifest.json")
    if not os.path.isfile(manifest_path):
        raise RestoreError(f"{directory}: no manifest.json — incomplete snapshot, refusing to restore from it")
    snap = {"_manifest": json.load(open(manifest_path))}
    for name in os.listdir(directory):
        if name.endswith(".json.gz"):
            with open(os.path.join(directory, name), "rb") as fh:
                snap[name[: -len(".json.gz")]] = json.loads(gzip.decompress(fh.read()))
    return snap


def _lookup(snap, identifiers):
    by_ident = {i["identifier"]: i for i in snap.get("issues") or []}
    missing = [x for x in identifiers if x not in by_ident]
    if missing:
        raise RestoreError(f"not in the snapshot: {', '.join(missing)}")
    return [by_ident[x] for x in identifiers]


def select_issues(snap, identifiers):
    """The named issues, parents before children (a child's parentId must already exist when it is created)."""
    chosen = _lookup(snap, identifiers)
    parent_of = {i["id"]: (i.get("parent") or {}).get("id") for i in chosen}

    def depth(issue_id):
        parent = parent_of.get(issue_id)
        return 1 + depth(parent) if parent in parent_of else 0

    return sorted(chosen, key=lambda i: depth(i["id"]))


def _users(snap):
    return {u["id"]: u.get("name") or u.get("displayName") or u["id"] for u in snap.get("users") or []}


def comments_for(snap, issue_id):
    return sorted((c for c in snap.get("comments") or [] if (c.get("issue") or {}).get("id") == issue_id),
                  key=lambda c: c["createdAt"])


# --- mapping ----------------------------------------------------------------------------------------------------

def state_map(snap, target_states):
    """Snapshot state id -> target state id: same name first, else the first target state of the same type."""
    by_name = {s["name"]: s["id"] for s in target_states}
    by_type = {}
    for s in target_states:
        by_type.setdefault(s["type"], s["id"])
    out = {}
    for s in snap.get("workflowStates") or []:
        target = by_name.get(s["name"]) or by_type.get(s["type"])
        if target:
            out[s["id"]] = target
    return out


@dataclasses.dataclass
class RestoreContext:
    snapshot: dict
    team_id: str
    states: dict
    id_map: dict
    snapshot_ts: str


def _provenance(what, snapshot_ts, extra):
    return f"{PROVENANCE_PREFIX} from snapshot `{snapshot_ts}` — {what}{extra}."


def strip_provenance(text):
    """The original text back out of a restored description/comment (the header ends at the first blank line)."""
    if not text or not text.startswith(PROVENANCE_PREFIX):
        return text or ""
    parts = text.split("\n\n", 1)
    return parts[1] if len(parts) > 1 else ""


def neutralize_mentions(text):
    """`@name` -> `@<word-joiner>name`. Restoring a mention verbatim re-invokes agents (the first live drill re-ran
    SpecBot on every `@SpecBot` in EMA-240's comments). The joiner is invisible and `_norm` removes it, so verification
    still compares the text as equal."""
    return re.sub(r"@(?=[A-Za-z0-9_])", "@" + WORD_JOINER, text or "")


def _label_problem(label):
    """Why a label cannot be restored, or None when it can (workspace-scoped and live)."""
    if label.get("team"):
        return "team-scoped"
    if label.get("archivedAt") or label.get("retiredAt"):
        return "archived"
    return None


def _labels(issue, snap, dropped):
    labels = {lab["id"]: lab for lab in snap.get("issueLabels") or []}
    keep = []
    for lid in issue.get("labelIds") or []:
        lab = labels.get(lid)
        problem = "not in snapshot" if lab is None else _label_problem(lab)
        if problem:
            dropped.append(f"label {lab['name'] if lab else lid} ({problem})")
        else:
            keep.append(lid)
    return keep


def _optional_fields(issue, ctx, inp, dropped):
    """Due date and parent when restorable; every field the target cannot hold goes into `dropped`."""
    if issue.get("dueDate"):
        inp["dueDate"] = issue["dueDate"]
    parent = (issue.get("parent") or {}).get("id")
    if parent in ctx.id_map:
        inp["parentId"] = ctx.id_map[parent]
    elif parent:
        dropped.append("parent (not restored)")
    dropped.extend(label for field, label in DROPPABLE if issue.get(field))
    if issue.get("estimate") is not None:
        dropped.append("estimate")


def build_issue_input(issue, ctx):
    """(IssueCreateInput, dropped-field notes). Raises when the state cannot be mapped at all."""
    state = ctx.states.get((issue.get("state") or {}).get("id"))
    if not state:
        raise RestoreError(f"{issue['identifier']}: its workflow state has no match in the target team")
    author = _users(ctx.snapshot).get((issue.get("creator") or {}).get("id"), "unknown")
    header = _provenance(f"originally `{issue['identifier']}`", ctx.snapshot_ts,
                         f", created {issue.get('createdAt')} by {author}")
    dropped = []
    inp = {"teamId": ctx.team_id, "title": issue["title"], "priority": issue.get("priority") or 0,
           "stateId": state, "description": f"{header}\n\n{neutralize_mentions(issue.get('description'))}",
           "labelIds": _labels(issue, ctx.snapshot, dropped)}
    _optional_fields(issue, ctx, inp, dropped)
    return inp, dropped


def build_comment_input(comment, new_issue_id, comment_map, snap):
    author = ((comment.get("botActor") or {}).get("name")
              or _users(snap).get((comment.get("user") or {}).get("id"), "unknown"))
    header = _provenance(f"originally by {author}", snap["_manifest"].get("started_at", "?"),
                         f" on {comment.get('createdAt')}")
    inp = {"issueId": new_issue_id, "body": f"{header}\n\n{neutralize_mentions(comment.get('body'))}"}
    parent = (comment.get("parent") or {}).get("id")
    if parent in comment_map:
        inp["parentId"] = comment_map[parent]
    return inp


# --- verification -----------------------------------------------------------------------------------------------

def _norm(text):
    """Linear re-renders stored markdown (bullets `-` -> `*`, escapes, trailing space); compare the meaning, not bytes."""
    text = (text or "").replace(WORD_JOINER, "")
    text = re.sub(r"\\([\\`*_{}\[\]()#+\-.!|~>])", r"\1", text)   # Linear backslash-escapes markdown punctuation
    lines = []
    for line in text.splitlines():
        stripped = line.rstrip()
        if stripped.lstrip().startswith("- "):
            stripped = stripped.replace("- ", "* ", 1)
        lines.append(stripped)
    return "\n".join(lines).strip()


@dataclasses.dataclass
class VerifyContext:
    snapshot: dict
    id_map: dict
    target_states: list


def _check_fields(original, readback):
    ident, bad = original["identifier"], []
    if readback.get("title") != original["title"]:
        bad.append(f"{ident}: title {readback.get('title')!r} != {original['title']!r}")
    if _norm(strip_provenance(readback.get("description"))) != _norm(original.get("description")):
        bad.append(f"{ident}: description differs")
    got_priority, want_priority = readback.get("priority") or 0, original.get("priority") or 0
    if got_priority != want_priority:
        bad.append(f"{ident}: priority {readback.get('priority')} != {original.get('priority')}")
    return bad


def _check_state_and_parent(original, readback, ctx):
    ident, bad = original["identifier"], []
    expected_state = state_map(ctx.snapshot, ctx.target_states).get((original.get("state") or {}).get("id"))
    expected_type = next((s["type"] for s in ctx.target_states if s["id"] == expected_state), None)
    got_type = (readback.get("state") or {}).get("type")
    if got_type != expected_type:
        bad.append(f"{ident}: state type {got_type} != {expected_type}")
    want_parent = ctx.id_map.get((original.get("parent") or {}).get("id"))
    got_parent = (readback.get("parent") or {}).get("id")
    if got_parent != want_parent:
        bad.append(f"{ident}: parent {got_parent} != {want_parent}")
    return bad


def _check_comments(original, readback, snap):
    # Comments written by bots/agents are not part of the restore (SpecBot auto-reviews every new issue).
    human = [c for c in readback.get("comments") or [] if not c.get("botActor")]
    got = [_norm(strip_provenance(c["body"])) for c in sorted(human, key=lambda c: c["createdAt"])]
    want = [_norm(c.get("body")) for c in comments_for(snap, original["id"])]
    if got == want:
        return []
    return [f"{original['identifier']}: comments {len(got)} restored vs {len(want)} in snapshot (or bodies differ)"]


def verify(original, readback, ctx):
    """Every field the restore promised, compared against the snapshot. Returns human-readable mismatches."""
    return (_check_fields(original, readback) + _check_state_and_parent(original, readback, ctx)
            + _check_comments(original, readback, ctx.snapshot))


# --- restore + drill --------------------------------------------------------------------------------------------

ISSUE_CREATE = "mutation($i: IssueCreateInput!){ issueCreate(input:$i){ success issue{ id identifier } } }"
COMMENT_CREATE = "mutation($i: CommentCreateInput!){ commentCreate(input:$i){ success comment{ id } } }"
READBACK = ("query($id: String!){ issue(id:$id){ identifier title description priority state{ type } parent{ id } "
            "comments(first: 250){ nodes{ id body createdAt parent{ id } user{ name } botActor{ name } } } } }")


@dataclasses.dataclass
class Target:
    """Where a restore goes: the team, its workflow states, and the snapshot label for provenance."""
    team_id: str
    states: list
    snapshot_ts: str
    created: list = dataclasses.field(default_factory=list)


def _restore_comments(post, snap, issue_id, new_issue_id):
    comment_map = {}
    for comment in comments_for(snap, issue_id):
        out = post(COMMENT_CREATE, {"i": build_comment_input(comment, new_issue_id, comment_map, snap)})
        if not out["commentCreate"].get("success"):
            raise RestoreError(f"commentCreate failed on issue {issue_id}")
        comment_map[comment["id"]] = out["commentCreate"]["comment"]["id"]
    return len(comment_map)


def restore(post, snap, identifiers, target):
    """Create the issues and their comments in the target team. Appends every new issue id to `target.created` AS it is
    made, so a caller's teardown can remove partial work. Returns (id_map, dropped-by-identifier, comment count)."""
    ctx = RestoreContext(snap, target.team_id, state_map(snap, target.states), {}, target.snapshot_ts)
    dropped, n_comments = {}, 0
    for issue in select_issues(snap, identifiers):
        inp, dropped[issue["identifier"]] = build_issue_input(issue, ctx)
        res = post(ISSUE_CREATE, {"i": inp})["issueCreate"]
        if not res.get("success"):
            raise RestoreError(f"issueCreate failed for {issue['identifier']}")
        ctx.id_map[issue["id"]] = res["issue"]["id"]
        target.created.append(res["issue"]["id"])
        n_comments += _restore_comments(post, snap, issue["id"], res["issue"]["id"])
    return ctx.id_map, dropped, n_comments


def _readback(post, new_id):
    issue = post(READBACK, {"id": new_id})["issue"]
    issue["comments"] = (issue.get("comments") or {}).get("nodes") or []
    return issue


def verify_all(post, identifiers, ctx):
    snap = ctx.snapshot
    return [m for issue in select_issues(snap, identifiers)
            for m in verify(issue, _readback(post, ctx.id_map[issue["id"]]), ctx)]


@dataclasses.dataclass
class DrillOptions:
    snapshot_ts: str
    key: str = "RDRL"
    keep: bool = False


def drill(post, snap, identifiers, opts):
    """Scratch team -> restore -> read back + verify -> delete the issues and the team, ALWAYS (try/finally)."""
    team = post("mutation($i: TeamCreateInput!){ teamCreate(input:$i){ success team{ id key states{ nodes{ id name "
                "type } } } } }", {"i": {"name": f"Restore drill {opts.snapshot_ts}", "key": opts.key}})["teamCreate"]["team"]
    target = Target(team["id"], team["states"]["nodes"], opts.snapshot_ts)
    report = {"restored": [], "comments": 0, "dropped": {}, "mismatches": [], "teardown_errors": []}
    try:
        id_map, report["dropped"], report["comments"] = restore(post, snap, identifiers, target)
        report["restored"] = [i["identifier"] for i in select_issues(snap, identifiers)]
        report["mismatches"] = verify_all(post, identifiers, VerifyContext(snap, id_map, target.states))
    finally:
        if opts.keep:   # diagnosis only: leave the scratch team + issues for inspection; the caller must clean up
            report["kept"] = {"team": team["key"], "issues": target.created}
        else:
            _teardown(post, team, target.created, report)
    return report


def _teardown(post, team, created, report):
    """Delete the restored issues (children first) and then the scratch team; record, never raise, each failure."""
    for new_id in reversed(created):
        try:
            post("mutation($id: String!){ issueDelete(id:$id){ success } }", {"id": new_id})
        except RestoreError as exc:
            report["teardown_errors"].append(f"issue {new_id}: {exc}")
    try:
        post("mutation($id: String!){ teamDelete(id:$id){ success } }", {"id": team["id"]})
    except RestoreError as exc:
        report["teardown_errors"].append(f"team {team['key']}: {exc}")


def _run(args):
    snap = load_snapshot(args.snapshot)
    ts = snap["_manifest"].get("started_at") or os.path.basename(os.path.normpath(args.snapshot))
    identifiers = [x.strip() for x in args.issues.split(",") if x.strip()]
    if args.drill:
        return drill(gql, snap, identifiers, DrillOptions(ts, args.key, args.keep))
    states = gql("query($id: String!){ team(id:$id){ states{ nodes{ id name type } } } }",
                 {"id": args.team_id})["team"]["states"]["nodes"]
    target = Target(args.team_id, states, ts)
    id_map, dropped, n = restore(gql, snap, identifiers, target)
    return {"restored": identifiers, "comments": n, "dropped": dropped, "new_ids": target.created,
            "mismatches": verify_all(gql, identifiers, VerifyContext(snap, id_map, states)), "teardown_errors": []}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--snapshot", required=True, help="downloaded snapshot directory (with manifest.json)")
    ap.add_argument("--issues", required=True, help="comma-separated identifiers, e.g. EMA-54,EMA-13")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--drill", action="store_true", help="scratch team, verify, then delete everything")
    mode.add_argument("--team-id", help="restore into this existing team and keep the result")
    ap.add_argument("--key", default="RDRL", help="scratch team key for --drill")
    ap.add_argument("--keep", action="store_true", help="--drill only: skip teardown to inspect (clean up after!)")
    args = ap.parse_args(argv)
    try:
        report = _run(args)
    except RestoreError as exc:
        print(f"CANNOT RUN: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2))
    return 1 if report["mismatches"] or report["teardown_errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
