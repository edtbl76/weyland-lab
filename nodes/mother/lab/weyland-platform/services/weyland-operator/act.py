"""App-side act executor for the operator (B66 Part 3) — the confirm-step's FIRE half.

The LLM can only PROPOSE (see tools.propose_act); THIS module fires, and only the app calls it, only after an
explicit user 'yes'. Fail-closed: an unknown tool or a job_name off the allowlist is refused here before any HTTP
call. The tool-server runs its own Hook.ACT guard on the actual launch — the deeper rail."""
import os

import httpx

TOOLSERVER = os.getenv("TOOLSERVER", "http://weyland-tool-server.weyland.svc.cluster.local:8080")
ACT_TIMEOUT = float(os.getenv("ACT_TIMEOUT", "30"))

# The 3 Dagster jobs the tool-server will launch (mirrors its PipelineTriggerRequest Literal).
JOB_ALLOWLIST = {"weyland_ingestion_job", "weyland_eval_job", "weyland_eval_score_job"}

# tool -> (tool-server endpoint, needs a job_name)
CATALOG = {
    "pipeline_trigger": ("/pipeline/trigger", True),
    "evals_run": ("/evals/run", False),
    "evals_score": ("/evals/score", False),
}


def describe(proposal: dict) -> str:
    """One-line human description of a proposal for the confirm prompt."""
    tool = proposal.get("tool", "?")
    job = proposal.get("job_name") or ""
    summary = (proposal.get("summary") or "").strip()
    detail = tool + (f" (job: {job})" if job else "")
    return f"{summary} — will run `{detail}`" if summary else f"will run `{detail}`"


def fire(proposal: dict, actor: str | None) -> str:
    """Execute a confirmed proposal. Returns a human result string. Fail-closed on unknown tool / bad job_name."""
    tool = proposal.get("tool")
    if tool not in CATALOG:
        return f"⛔ Unknown action `{tool}` — refused."
    path, needs_job = CATALOG[tool]
    body = {}
    if needs_job:
        job = proposal.get("job_name")
        if job not in JOB_ALLOWLIST:
            return f"⛔ Job `{job}` is not on the allowlist — refused."
        body["job_name"] = job
    try:
        r = httpx.post(f"{TOOLSERVER}{path}", json=body,
                       headers={"X-Forwarded-Consumer": actor or "operator:unknown"}, timeout=ACT_TIMEOUT)
    except Exception as exc:
        return f"⚠️ Action failed to reach the tool-server: {exc}"
    if r.status_code >= 400:
        return f"⚠️ Action rejected ({r.status_code}): {r.text}"
    data = r.json()
    return f"✅ Launched `{data.get('job_name', tool)}` — run {data.get('run_id', '?')}. Track it in Dagster."
