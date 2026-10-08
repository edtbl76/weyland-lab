#!/usr/bin/env python3
"""B175 — publish the loop library into Bifrost's Prompt Repository (folder `loop-library`, prompt `loop-<id>`).

Source of truth: knowledge-repos/loop-library/*.md in git. This image cannot read that directory, so it reads the
bundled copy beside this script (loop_library.json, written by scripts/embed-loops.sh; CI's check-loop-library.sh
fails while it is stale). Run by the Dagster `registrations` group (asset bifrost_loops_registered, weekly + on
demand, which passes BIFROST_URL), or by hand:
    kubectl -n weyland exec deploy/dagster-user-code -- env BIFROST_URL=http://bifrost.weyland.svc.cluster.local:8080 python /app/scripts/register_bifrost_loops.py

Unlike register_bifrost_prompts.py, which skips an existing prompt, git wins here: a loop whose published text
differs from the bundle gets a NEW VERSION; an unchanged loop posts nothing (no churn). A published `loop-*` prompt
no longer in git is REPORTED as an orphan, never deleted automatically. Any failed POST fails the run (exit 1).
API shapes observed live 2026-10-08 (see register_bifrost_prompts.py for the contract): versions come back as
{"versions":[{is_latest, messages:[{message:{role, content}}]}]}. `{{var}}` placeholders in a loop are auto-extracted
by Bifrost as variables; never send a `variables` field (it 400s).
"""
import json
import os
import sys
from pathlib import Path

BASE_ENV = "BIFROST_URL"   # required: set by the Dagster asset (registrations.py); no default, so a typo fails loudly
BUNDLE = Path(__file__).resolve().parent / "loop_library.json"
FOLDER = "loop-library"
FOLDER_DESCRIPTION = ("Reusable agent loops (B175): a prompt with checkpoints and an explicit terminal condition. "
                      "Source of truth: knowledge-repos/loop-library in git — edit there, not here.")
PREFIX = "loop-"
BIFROST_HEADERS = {"X-Bifrost-Setup-Token": os.environ["BIFROST_SETUP_TOKEN"]} if os.getenv("BIFROST_SETUP_TOKEN") else {}  # B202: v2.2.6+ setup lock (auth off)
API = "/api/prompt-repo"


def read_bundle(path: Path = BUNDLE) -> list[dict]:
    loops = json.loads(path.read_text()).get("loops") or []
    if not loops:
        raise ValueError(f"{path} holds no loops — refusing to publish an empty library")
    return loops


def message(loop: dict) -> str:
    """The published prompt text: what the loop is and when it stops, then the full prompt."""
    return (f"# {loop['title']} ({loop['category']})\n\n{loop['description']}\n\n"
            f"Stop when: {loop['terminal_condition']}\n\n{loop['prompt']}\n")


def _latest_content(versions: list[dict]) -> str | None:
    for version in versions:
        if version.get("is_latest"):
            return "".join(m.get("message", {}).get("content", "") for m in version.get("messages") or [])
    return None


def _ensure_folder(client, summary: dict) -> str | None:
    folders = {f["name"]: f["id"] for f in client.get(f"{API}/folders").get("folders") or []}
    if FOLDER in folders:
        return folders[FOLDER]
    status, body = client.post(f"{API}/folders", {"name": FOLDER, "description": FOLDER_DESCRIPTION})
    if status >= 300:
        summary["failed"] += 1
        print(f"folder  FAILED {FOLDER}: {body}")
        return None
    print(f"folder  CREATED {FOLDER}")
    return body["folder"]["id"]


def _publish_one(client, loop: dict, pid: str | None, folder_id: str) -> str:
    """Publish one loop. Returns created / updated / unchanged / failed."""
    name, text = PREFIX + loop["id"], message(loop)
    if pid is None:
        status, body = client.post(f"{API}/prompts", {"name": name, "folder_id": folder_id})
        if status >= 300:
            print(f"prompt  FAILED {name}: {body}")
            return "failed"
        pid, action = body["prompt"]["id"], "created"
    elif _latest_content(client.get(f"{API}/prompts/{pid}/versions").get("versions") or []) == text:
        return "unchanged"
    else:
        action = "updated"
    status, body = client.post(f"{API}/prompts/{pid}/versions", {
        "commit_message": f"{loop['category']} loop from git (knowledge-repos/loop-library/{loop['id']}.md)",
        "messages": [{"role": "user", "content": text}],
    })
    if status >= 300:
        print(f"prompt  FAILED {name} version: {body}")
        return "failed"
    print(f"prompt  {action.upper()} {FOLDER}/{name}")
    return action


def publish(client, loops: list[dict]) -> dict:
    """Reconcile the folder against `loops`. `client` has get(path) -> json and post(path, body) -> (status, json)."""
    summary = {"created": 0, "updated": 0, "unchanged": 0, "failed": 0, "orphans": []}
    folder_id = _ensure_folder(client, summary)
    if folder_id is None:
        return summary
    # limit=1000 like realm_roles_registered: a capped page would hide an existing loop and re-create it
    published = {p["name"]: p["id"] for p in client.get(f"{API}/prompts?limit=1000").get("prompts") or []
                 if p.get("folder_id") == folder_id}
    for loop in loops:
        summary[_publish_one(client, loop, published.get(PREFIX + loop["id"]), folder_id)] += 1
    summary["orphans"] = sorted(set(published) - {PREFIX + loop["id"] for loop in loops})
    for orphan in summary["orphans"]:
        print(f"prompt  ORPHAN {FOLDER}/{orphan} — no longer in git; delete it in the Bifrost UI if retired")
    return summary


def exit_code(summary: dict) -> int:
    return 1 if summary["failed"] else 0


class _Http:
    """The real client: httpx against Bifrost, only imported when run (the test lane has no httpx)."""

    def __init__(self, base: str):
        import httpx
        self._c = httpx.Client(base_url=base, timeout=30, headers=BIFROST_HEADERS)

    def get(self, path):
        r = self._c.get(path)
        r.raise_for_status()
        return r.json()

    def post(self, path, body):
        r = self._c.post(path, json=body)
        try:
            return r.status_code, r.json()
        except ValueError:
            return r.status_code, {"text": r.text[:200]}


def main() -> int:
    base = os.getenv(BASE_ENV)
    if not base:
        print(f"register_bifrost_loops: {BASE_ENV} is not set — the Dagster asset passes it; by hand, see the docstring",
              file=sys.stderr)
        return 2
    loops = read_bundle()
    summary = publish(_Http(base), loops)
    print(f"\ndone. {summary['created']} created, {summary['updated']} updated, {summary['unchanged']} unchanged, "
          f"{summary['failed']} failed, {len(summary['orphans'])} orphan(s). {len(loops)} loops in git.")
    return exit_code(summary)


if __name__ == "__main__":
    sys.exit(main())
