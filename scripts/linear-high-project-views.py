"""Build + verify the Linear "High · <project>" workspace view set (B119).

Usage:  set -a && . scripts/.env && set +a && python3 scripts/linear-high-project-views.py
        Needs the WRITE-capable LINEAR_API_KEY (the CI key is read-only by design).
        Exit 0 = every view exists AND its issue count matches an independent query.

One `High · <project>` view per LIVE project (filtered by project ID, so a rename doesn't break it) plus a
`High — all projects` index grouped by project. Idempotent by name: existing views are skipped, never duplicated.
Fail-closed: any GraphQL error, a `success:false`, zero projects, or a count mismatch exits non-zero.

Re-run after creating any Linear project — scripts/onboard-repo.sh prints the step. `High · OJay Floyd` was missing
on 2026-09-24 because this lived in a scratch dir, so nothing prompted a re-run. Views stay WORKSPACE-scoped (no
teamId): one team, many initiatives; a team-scoped view shows only on the team page (B119, 2026-09-25).
"""
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.linear.app/graphql"
OPEN_HIGH = {"state": {"type": {"nin": ["completed", "canceled", "duplicate"]}}, "priority": {"eq": 2}}
CREATE = "mutation($i: CustomViewCreateInput!){ customViewCreate(input:$i){ success customView{ id name } } }"
PREFS = "mutation($i: ViewPreferencesCreateInput!){ viewPreferencesCreate(input:$i){ success } }"
VIEW_ISSUES = "query($id:String!){ customView(id:$id){ issues(first:100){ nodes{ id } } } }"
VIEW_GROUPING = "query($id:String!){ customView(id:$id){ viewPreferencesValues{ issueGrouping } } }"
INDEPENDENT = ('{ issues(first:250, filter:{state:{type:{nin:["completed","canceled","duplicate"]}}, '
               'priority:{eq:2}}){ nodes{ project{ id } } } }')


def gql(query, variables=None):
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Authorization": os.environ["LINEAR_API_KEY"], "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as exc:
        sys.exit(f"HTTP {exc.code}: {exc.read()[:300].decode(errors='replace')}")
    if "errors" in data:
        sys.exit("GraphQL error: " + json.dumps(data["errors"])[:500])
    return data["data"]


def ensure(existing, name, desc, flt):
    """Return the id of the view called `name`, creating it if absent."""
    if name in existing:
        print(f"SKIP  {name}")
        return existing[name]
    res = gql(CREATE, {"i": {"name": name, "description": desc, "filterData": flt, "shared": True}})["customViewCreate"]
    if not res["success"]:
        sys.exit(f"success=false creating {name}")
    print(f"MADE  {name}")
    return res["customView"]["id"]


def count_view(view_id):
    return len(gql(VIEW_ISSUES, {"id": view_id})["customView"]["issues"]["nodes"])


def main():
    projects = [p for p in gql("{ projects(first:50){ nodes{ id name status{type} } } }")["projects"]["nodes"]
                if p["status"]["type"] not in ("completed", "canceled")]
    if not projects:
        sys.exit("no live projects returned — refusing to build or verify an empty set")
    existing = {v["name"]: v["id"] for v in gql("{ customViews(first:100){ nodes{ id name } } }")["customViews"]["nodes"]}

    made = {}
    for proj in sorted(projects, key=lambda p: p["name"].lower()):
        view_id = ensure(existing, f"High · {proj['name']}",
                         f"Open High-priority issues in the {proj['name']} project (filtered by project ID — survives a rename).",
                         {**OPEN_HIGH, "project": {"id": {"eq": proj["id"]}}})
        made[proj["name"]] = (view_id, proj["id"])

    index = ensure(existing, "High — all projects",
                   "Every open High-priority issue, grouped by project — the index for the High · <project> set.", OPEN_HIGH)
    # Only when not already grouped — viewPreferencesCreate on every run would stack duplicate preference rows.
    if gql(VIEW_GROUPING, {"id": index})["customView"]["viewPreferencesValues"].get("issueGrouping") != "project":
        gql(PREFS, {"i": {"type": "organization", "viewType": "customView", "customViewId": index,
                          "preferences": {"issueGrouping": "project", "viewOrdering": "priority"}}})

    # Verify every view against an INDEPENDENT count (a plain issues query, not the view itself).
    independent = gql(INDEPENDENT)["issues"]["nodes"]
    by_project = {}
    for node in independent:
        pid = (node["project"] or {}).get("id")
        by_project[pid] = by_project.get(pid, 0) + 1
    bad = 0
    for name, (view_id, pid) in made.items():
        got, want = count_view(view_id), by_project.get(pid, 0)
        bad += got != want
        print(f"  {'OK ' if got == want else 'BAD'} High · {name:40} view={got:2} independent={want}")
    got, want = count_view(index), len(independent)
    bad += got != want
    print(f"  {'OK ' if got == want else 'BAD'} High — all projects{'':27} view={got:2} independent={want}")
    grouping = gql(VIEW_GROUPING, {"id": index})["customView"]["viewPreferencesValues"]
    print("  index grouping:", grouping)
    sys.exit(1 if bad or grouping.get("issueGrouping") != "project" else 0)


if __name__ == "__main__":
    main()
