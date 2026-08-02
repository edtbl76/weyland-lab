"""Gná — the dispatcher.

Given a free-text task, Gná picks the single best agent from the roster and runs it. It classifies with a fast lane
(`wl-speed`) over the roster's plain-English descriptions, then hands off. Fail-safe: an unparseable/unknown answer
routes to Odin (the engineering orchestrator), who can always decompose or redirect.

`run_agent` is the shared entry point everything uses: a lead delegates to its members; a plain agent answers directly."""
from llm import brain
from obs import log
from realms import run_lead
from agents import run_solo
from roster import BY_KEY, ROSTER, AgentSpec

_CATALOG = "\n".join(f"- {a.key}: {a.god} ({a.realm}/{a.role}) — {a.what}" for a in ROSTER)
_CLASSIFY = (
    "You are Gná, the dispatcher for the weyland Realm of Agents. Choose the ONE agent best suited to the task. "
    "Reply with ONLY its key (the token before the colon), nothing else.\n\nAgents:\n" + _CATALOG
)


async def run_agent(spec: AgentSpec, task: str, history: list | None = None) -> str:
    log(f"running {spec.god} ({'lead' if spec.lead else 'solo'})")
    if spec.lead:
        return await run_lead(spec, task, history)
    return await run_solo(spec, task, history)


async def classify(task: str) -> str:
    """Return the roster key of the best-fit agent (fail-safe to 'odin')."""
    try:
        resp = await brain("wl-speed").ainvoke([("system", _CLASSIFY), ("user", task)])
        key = (resp.content or "").strip().split()[0].strip(".,:`\"'").lower()
        if key in BY_KEY:
            log(f"Gná routed → {key}")
            return key
    except Exception as exc:
        log(f"Gná classify failed, routing to odin: {exc}")
    return "odin"


async def dispatch(task: str, history: list | None = None) -> tuple[str, str]:
    """Classify → run. Returns (chosen_key, answer)."""
    key = await classify(task)
    return key, await run_agent(BY_KEY[key], task, history)
