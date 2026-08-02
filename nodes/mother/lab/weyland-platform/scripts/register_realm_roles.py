#!/usr/bin/env python3
"""Register the Realm-of-Agents role prompts into the Bifrost Prompt Repository as `role-<key>` (B17 DoD).

Run FROM the realm pod so it reuses the LIVE `roles.py` / `roster.py` as the single source of truth (no duplication):
    kubectl -n weyland exec -i deploy/realm-of-agents -c realm-of-agents -- python - < nodes/mother/lab/weyland-platform/scripts/register_realm_roles.py

After this, the Realm's `prompts.load_role()` can resolve each agent's system prompt LIVE from Bifrost (TTL-cached),
so a prompt is editable in the Bifrost UI without a rebuild — fail-safe to the baked `roles.py` fallback if Bifrost is
unreachable or the prompt is unregistered. Idempotent: matched by name, existing prompts skipped. Mirrors the
`register_bifrost_prompts.py` API contract (POST /api/prompt-repo/{folders,prompts,prompts/{id}/versions}); the
prompt-repo API is un-authed in-cluster.
"""
import httpx

from config import BIFROST_API_URL
from roster import ROSTER, fallback_prompt

FOLDER = ("realm-of-agents",
          "Per-agent role/system prompts for the B17 Realm of Agents (role-<key>). The Realm fetches these live via "
          "prompts.load_role (TTL-cached, fail-safe to the baked fallback). Note: all agents run on Claude Haiku via "
          "the REALM_MODEL override; the lane recorded per prompt is the designed routing.")


def main():
    c = httpx.Client(base_url=BIFROST_API_URL, timeout=30)
    folders = {f["name"]: f["id"] for f in c.get("/api/prompt-repo/folders").json().get("folders") or []}
    if FOLDER[0] not in folders:
        folders[FOLDER[0]] = c.post("/api/prompt-repo/folders",
                                    json={"name": FOLDER[0], "description": FOLDER[1]}).json()["folder"]["id"]
        print(f"folder  CREATED {FOLDER[0]}")
    fid = folders[FOLDER[0]]
    existing = {p["name"] for p in c.get("/api/prompt-repo/prompts",
                                         params={"limit": 1000}).json().get("prompts") or []}
    created = skipped = 0
    for spec in ROSTER:
        name = f"role-{spec.key}"
        if name in existing:
            skipped += 1
            continue
        pid = c.post("/api/prompt-repo/prompts",
                     json={"name": name, "folder_id": fid}).json()["prompt"]["id"]
        r = c.post(f"/api/prompt-repo/prompts/{pid}/versions", json={
            "commit_message": f"realm: {spec.realm} · {spec.god} · {spec.role} · designed lane {spec.lane} "
                              f"(overridden to Claude Haiku via REALM_MODEL)",
            "messages": [{"role": "system", "content": fallback_prompt(spec)}],
        })
        ok = r.status_code < 300
        print(f"role  {'CREATED' if ok else 'FAILED '} {name}{'' if ok else ' ' + r.text[:120]}")
        created += ok
    print(f"\ndone. {created} created, {skipped} existing. {len(ROSTER)} role prompts in folder '{FOLDER[0]}'.")


if __name__ == "__main__":
    main()
