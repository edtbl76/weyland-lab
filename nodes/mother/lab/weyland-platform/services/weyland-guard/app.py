"""weyland-guard — the B14 guardrail layer, extracted from the tool-server into a shared service (B70 Part 1).

The `guardrails/` package is a VERBATIM copy of the tool-server's — same validators, same SHADOW-by-default
config, same Postgres verdict store — so verdicts are identical whichever caller invokes them. What changes is the
seam: instead of an in-process `_guard()` call, callers (tool-server, weyland-agent, the future B66 fleet) POST to
one of three typed routes. The 3 transformer models (LLM Guard injection + toxicity + NLI cross-encoder) load ONCE,
here, instead of once per consumer pod.

Because this service is async FastAPI (unlike the sync tool-server), the pipeline runs natively on the request
event loop — no background daemon-thread/`run_coroutine_threadsafe` hack. SHADOW validators still fire-and-forget
(telemetry only, ~zero added latency); FLAG/BLOCK run inline. A BLOCK returns decision="block" + the verdict; the
caller decides to 403. Callers treat an unreachable service as allow (client-side fail-open) — the guards are
advisory, they must never take an answer offline.
"""
import hmac
import os
from contextlib import asynccontextmanager

import psycopg2
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app
from pydantic import BaseModel, Field

from guardrails.config import hook_chain, set_override, clear_overrides, current_overrides, all_validators
from guardrails.pipeline import GuardrailPipeline
from guardrails.verdict import Decision, Hook, Mode
from guardrails import metrics as guard_metrics
from guardrails import store as guard_store

# Postgres (guardrail_verdicts) — same DB/secret keys the tool-server uses. STRICT mTLS → this pod is meshed.
PG_HOST = os.environ.get("WEYLAND_DB_HOST", "weyland-postgres.weyland.svc.cluster.local")
PG_PORT = int(os.environ.get("WEYLAND_DB_PORT", "5432"))
PG_DB = os.environ.get("WEYLAND_DB_NAME", "weyland")
PG_USER = os.environ.get("WEYLAND_DB_USER", "weyland")
PG_PASSWORD = os.environ.get("WEYLAND_DB_PASSWORD", "")

guardrails: GuardrailPipeline | None = None
_active: list[str] = []


def _record_verdict(hook, mode, verdict, request_id, actor=None) -> None:
    """Persist a verdict to Prometheus + the guardrail_verdicts table. Telemetry must never break a request,
    so every path is best-effort (mirrors the tool-server's `_record_verdict`)."""
    try:
        guard_metrics.observe(hook, mode, verdict)   # actor is high-cardinality — DB only, never a metric label
    except Exception:
        pass
    try:
        with psycopg2.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER,
            password=PG_PASSWORD, connect_timeout=5,
        ) as conn:
            guard_store.record_verdict(conn, request_id=request_id, hook=hook, mode=mode, verdict=verdict, actor=actor)
    except Exception:
        pass


def _build_guardrails() -> GuardrailPipeline:
    """Instantiate the validator set — each loads its own baked model; a failure skips that one and the rest still
    run (partial coverage beats none). Identical construction to the tool-server's `_build_guardrails`."""
    from guardrails.validators.grounding import GroundingValidator
    from guardrails.validators.llm_guard import InjectionValidator, PIIValidator, ToxicityValidator
    from guardrails.validators.policy import AuditValidator, PolicyGateValidator

    builders = {
        "llm_guard.injection": InjectionValidator,
        "llm_guard.pii": PIIValidator,
        "llm_guard.toxicity": ToxicityValidator,
        "grounding.nli": GroundingValidator,
        "policy.audit": AuditValidator,
        "policy.gate": PolicyGateValidator,
    }
    validators = {}
    for name, builder in builders.items():
        try:
            validators[name] = builder()
        except Exception as exc:  # e.g. PII/Sensitive is intentionally not baked → skipped
            print(f"[guardrails] validator '{name}' unavailable: {exc}", flush=True)
    print(f"[guardrails] active validators: {sorted(validators)}", flush=True)
    return GuardrailPipeline(validators, hook_chain, _record_verdict)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global guardrails, _active
    try:
        guardrails = _build_guardrails()
        _active = sorted(guardrails._validators)
    except Exception as exc:  # advisory — never block startup
        print(f"[guardrails] disabled — failed to initialize: {exc}", flush=True)
        guardrails = None
    yield
    if guardrails:
        await guardrails.drain()


app = FastAPI(title="Weyland Guard", lifespan=lifespan)
app.mount("/metrics", make_asgi_app())


class GuardResponse(BaseModel):
    request_id: str
    decision: str                 # "allow" | "block"
    verdict: dict | None = None   # the blocking verdict, only when decision == "block"


async def _run(hook: Hook, request_id: str, payload: dict, actor: str | None) -> GuardResponse:
    if guardrails is None:
        return GuardResponse(request_id=request_id, decision="allow")
    blocked = await guardrails.run(hook, request_id, payload, actor)
    if blocked is not None and blocked.decision == Decision.BLOCK:
        return GuardResponse(
            request_id=request_id,
            decision="block",
            verdict={"validator": blocked.validator, "decision": blocked.decision.value,
                     "score": blocked.score, "reason": blocked.reason},
        )
    return GuardResponse(request_id=request_id, decision="allow")


class InputRequest(BaseModel):
    request_id: str
    query: str
    actor: str | None = None


class OutputRequest(BaseModel):
    request_id: str
    answer: str
    sources: list[dict] = Field(default_factory=list)   # [{content, ...}] — grounding.nli needs these
    actor: str | None = None


class ActRequest(BaseModel):
    request_id: str
    tool: str
    params: dict = Field(default_factory=dict)
    actor: str | None = None


@app.post("/guard/input", response_model=GuardResponse)
async def guard_input(req: InputRequest):
    return await _run(Hook.INPUT, req.request_id, {"query": req.query}, req.actor)


@app.post("/guard/output", response_model=GuardResponse)
async def guard_output(req: OutputRequest):
    return await _run(Hook.OUTPUT, req.request_id, {"answer": req.answer, "sources": req.sources}, req.actor)


@app.post("/guard/act", response_model=GuardResponse)
async def guard_act(req: ActRequest):
    # actor goes into the payload too (not just the recording arg) so policy.gate can enforce per-actor.
    return await _run(Hook.ACT, req.request_id,
                      {"tool": req.tool, "params": req.params, "actor": req.actor}, req.actor)


@app.get("/health")
async def health():
    """Liveness — the process is up. 200 even when guardrails failed to load (the service still answers 'allow')."""
    return {"status": "ok", "validators": _active}


@app.get("/ready")
async def ready():
    """Readiness — models loaded. 503 until the validator set is built, so traffic only arrives once the guard can
    actually score (a permanent model-load failure keeps the pod NotReady, which is correct — surface it, don't hide it)."""
    if guardrails is None:
        return JSONResponse(status_code=503, content={"status": "loading", "validators": []})
    return {"status": "ready", "validators": _active}


# --- Demo toggle: flip validator modes LIVE (in-process; no restart, no manifest drift → Argo-safe) ---------
# The toggle can DISABLE the guards, so /admin/* is auth-gated (unlike the scoring routes). Bearer token vs a
# k8s-Secret-injected value, constant-time compared, FAIL-CLOSED: if GUARD_ADMIN_TOKEN is unset the admin routes
# are inert (503), so an unconfigured deploy can't be toggled by any in-cluster caller.
ADMIN_TOKEN = os.environ.get("GUARD_ADMIN_TOKEN", "")


def verify_admin_token(authorization: str | None = Header(default=None)) -> None:
    if not ADMIN_TOKEN:
        raise HTTPException(status_code=503, detail="admin disabled: GUARD_ADMIN_TOKEN not configured")
    if not authorization or not hmac.compare_digest(authorization, f"Bearer {ADMIN_TOKEN}"):
        raise HTTPException(status_code=401, detail="unauthorized")


class ModeRequest(BaseModel):
    mode: str                              # off | shadow | flag | block
    validators: list[str] | None = None    # None = all validators


@app.post("/admin/mode", dependencies=[Depends(verify_admin_token)])
async def admin_set_mode(req: ModeRequest):
    """Temporarily un-shadow the guards for a demo, then revert with POST /admin/mode/reset. The override is
    in-process only, so a pod restart reverts to the committed modes (a demo can't be left on by accident)."""
    try:
        m = Mode(req.mode)
    except ValueError:
        return JSONResponse(status_code=400,
                            content={"error": f"bad mode {req.mode!r}; use off|shadow|flag|block"})
    targets = req.validators or all_validators()
    for name in targets:
        set_override(name, m)
    return {"applied": {"mode": m.value, "validators": targets}, "overrides": current_overrides()}


@app.post("/admin/mode/reset", dependencies=[Depends(verify_admin_token)])
async def admin_reset_mode():
    """Drop all demo overrides → back to the committed/env modes (everything SHADOW by default)."""
    clear_overrides()
    return {"overrides": current_overrides()}


@app.get("/admin/mode", dependencies=[Depends(verify_admin_token)])
async def admin_get_mode():
    """Current live overrides + the full validator set you can target."""
    return {"overrides": current_overrides(), "validators": all_validators()}
