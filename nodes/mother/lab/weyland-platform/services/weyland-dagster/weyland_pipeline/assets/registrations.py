"""B102 — the `registrations` reconcile group.

Declarative config that must be re-applied after a store/PVC reset (Bifrost prompt + skill repos, the Realm's role
prompts), folded into idempotent Dagster assets so it's GitOps-reproducible + scheduled instead of a manual
`kubectl exec`. Weekly reconcile + on-demand (`registrations_reconcile_job`).

- **bifrost_prompts / bifrost_skills** — shell out to the self-contained (httpx-only) register scripts bundled in the
  image at `/app/scripts/`; their hardcoded data is the source of truth, and each is idempotent (existing entries
  skipped, no version churn on re-run).
- **realm_roles** — the Realm owns its per-agent prompts (`roster.py`/`roles.py`), so we PULL them live from the Realm's
  `GET /prompts` and register each as `role-<key>` in the Bifrost prompt-repo — no prompt duplicated outside the Realm.

NOT here (on purpose): the MLflow prompt registry (`register_prompts.py`) — `mlflow` isn't in the Dagster env and adding
it risks the dagster+dbt+datahub version clashes the image already avoids; it stays a runbook. All targets are
in-cluster PERMISSIVE-mesh services, reachable from dagster-user-code over plain http.
"""
import os
import subprocess
import sys

import httpx
from dagster import Failure, MetadataValue, Output, asset

BIFROST_URL = os.getenv("BIFROST_URL", "http://bifrost.weyland.svc.cluster.local:8080")
REALM_URL = os.getenv("REALM_URL", "http://realm-of-agents.weyland.svc.cluster.local:8080")
_GROUP = "registrations"


def _run_script(name: str) -> Output:
    """Run a bundled, idempotent register_*.py and surface its output as asset metadata (its last line = the summary)."""
    proc = subprocess.run(
        [sys.executable, f"/app/scripts/{name}"],
        capture_output=True, text=True, timeout=300,
        env={**os.environ, "BIFROST_URL": BIFROST_URL},
    )
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    md = {"output": MetadataValue.md(f"```\n{out[-2000:]}\n```")}
    if proc.returncode != 0:
        raise Failure(description=f"{name} exited {proc.returncode}", metadata=md)
    summary = out.splitlines()[-1] if out else "(no output)"
    return Output(value=summary, metadata={"summary": summary, **md})


@asset(group_name=_GROUP,
       description="Reconcile the Bifrost Prompt Repository from the bundled register_bifrost_prompts.py (idempotent).")
def bifrost_prompts_registered() -> Output:
    return _run_script("register_bifrost_prompts.py")


@asset(group_name=_GROUP,
       deps=[bifrost_prompts_registered],
       description="B103 prompt federation — bidirectional sync (sync_prompts.py): pull native Langfuse/MLflow prompt "
                   "edits back to Bifrost, then mirror the Bifrost SoT out to Langfuse + MLflow. Runs AFTER the Bifrost "
                   "repo is reconciled. Uses the LANGFUSE_* env on the user-code pod (DefaultRunLauncher runs it here).")
def prompt_federation_synced() -> Output:
    return _run_script("sync_prompts.py")


@asset(group_name=_GROUP,
       description="Reconcile the Bifrost Skills Repository from the bundled register_bifrost_skills.py (idempotent).")
def bifrost_skills_registered() -> Output:
    return _run_script("register_bifrost_skills.py")


@asset(group_name=_GROUP,
       description="Reconcile the Realm's role-<key> prompts into Bifrost — pulled LIVE from the Realm /prompts "
                   "(the Realm stays the single source of truth; no prompt duplicated in the pipeline).")
def realm_roles_registered() -> Output:
    prompts = httpx.get(f"{REALM_URL}/prompts", timeout=30).json()
    c = httpx.Client(base_url=BIFROST_URL, timeout=30)
    fname = "realm-of-agents"
    folders = {f["name"]: f["id"] for f in c.get("/api/prompt-repo/folders").json().get("folders") or []}
    if fname not in folders:
        folders[fname] = c.post("/api/prompt-repo/folders", json={
            "name": fname,
            "description": "Per-agent role/system prompts for the B17 Realm of Agents (role-<key>), reconciled from the Realm /prompts.",
        }).json()["folder"]["id"]
    fid = folders[fname]
    existing = {p["name"] for p in c.get("/api/prompt-repo/prompts", params={"limit": 1000}).json().get("prompts") or []}
    created = skipped = 0
    for key, meta in prompts.items():
        name = f"role-{key}"
        if name in existing:
            skipped += 1
            continue
        pid = c.post("/api/prompt-repo/prompts", json={"name": name, "folder_id": fid}).json()["prompt"]["id"]
        c.post(f"/api/prompt-repo/prompts/{pid}/versions", json={
            "commit_message": f"realm: {meta.get('realm')} · {meta.get('god')} · {meta.get('role')} · lane "
                              f"{meta.get('lane')} (overridden to Claude Haiku via REALM_MODEL)",
            "messages": [{"role": "system", "content": meta.get("prompt", "")}],
        })
        created += 1
    summary = f"{created} created, {skipped} existing ({len(prompts)} roles)"
    return Output(value=summary, metadata={"created": created, "skipped": skipped, "roles": len(prompts), "summary": summary})
