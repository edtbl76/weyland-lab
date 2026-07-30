"""App-side act executor for the operator (B66 Part 3) — the confirm-step's FIRE half.

The LLM can only PROPOSE (see tools.propose_act); THIS module fires, and only the app calls it, only after an
explicit user 'yes'. Fail-closed: an unknown tool or a job_name off the allowlist is refused here before any HTTP
call. The tool-server runs its own Hook.ACT guard on the actual launch — the deeper rail."""
import os
import threading
import time

import httpx

TOOLSERVER = os.getenv("TOOLSERVER", "http://weyland-tool-server.weyland.svc.cluster.local:8080")
ACT_TIMEOUT = float(os.getenv("ACT_TIMEOUT", "30"))

# B17+B19: fire acts THROUGH the MCP gateway when a Keycloak client secret is wired — the gateway validates our
# client_credentials token and injects the VERIFIED actor (X-Forwarded-Consumer = weyland-operator). Without a secret we
# fall back to the legacy direct path (self-set actor) so the operator never hard-breaks mid-migration.
GATEWAY = os.getenv("GATEWAY_URL", "http://weyland-mcp-gateway.weyland.svc.cluster.local:8080")
KC_TOKEN_URL = os.getenv("KEYCLOAK_TOKEN_URL",
                         "http://keycloak.weyland.svc.cluster.local:8080/realms/weyland/protocol/openid-connect/token")
CLIENT_ID = os.getenv("OPERATOR_CLIENT_ID", "weyland-operator")
CLIENT_SECRET = os.getenv("OPERATOR_CLIENT_SECRET", "")

_tok = {"value": None, "exp": 0.0}
_tok_lock = threading.Lock()


def _token() -> str | None:
    """Cached client_credentials token (refreshed ~30s before expiry). None if no client secret is wired (→ legacy
    direct path) or the mint fails."""
    if not CLIENT_SECRET:
        return None
    with _tok_lock:
        if _tok["value"] and time.monotonic() < _tok["exp"]:
            return _tok["value"]
        try:
            r = httpx.post(KC_TOKEN_URL, data={"grant_type": "client_credentials",
                                               "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET}, timeout=10)
            r.raise_for_status()
            j = r.json()
        except Exception:
            return None
        _tok["value"] = j["access_token"]
        _tok["exp"] = time.monotonic() + max(30, int(j.get("expires_in", 300)) - 30)
        return _tok["value"]

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
    tok = _token()
    if tok:                                          # gateway path — the gateway sets the VERIFIED actor, we don't
        target, headers = GATEWAY, {"Authorization": f"Bearer {tok}"}
    else:                                            # legacy direct path — self-set actor (transitional)
        target, headers = TOOLSERVER, {"X-Forwarded-Consumer": actor or "operator:unknown"}
    try:
        r = httpx.post(f"{target}{path}", json=body, headers=headers, timeout=ACT_TIMEOUT)
    except Exception as exc:
        return f"⚠️ Action failed to reach the act surface: {exc}"
    if r.status_code >= 400:
        return f"⚠️ Action rejected ({r.status_code}): {r.text}"
    data = r.json()
    return f"✅ Launched `{data.get('job_name', tool)}` — run {data.get('run_id', '?')}. Track it in Dagster."
