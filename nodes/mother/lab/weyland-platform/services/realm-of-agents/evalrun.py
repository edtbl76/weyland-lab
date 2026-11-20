"""B253 (2026-11-20) — run one task in one arm of the Realm evaluation and report what it cost.

Arms (the question: does the Realm's shape beat one agent with the same tools and model?):
  realm   Gná routes, and a lead delegates to its members: the Realm as it is (router.dispatch).
  routed  Gná routes, and the chosen agent answers ALONE with its own tools, even a lead: routing without delegation.
  single  one generic agent holding every tool family the roster uses, no routing: the control.

Every arm runs free-only (budget.free_only: the local lane, LiteLLM fallbacks off, no paid tools), so an evaluation run
spends nothing whatever the caller sends. The counters ride the same per-request callback hook as Langfuse
(obs.extra_callbacks → obs.lf_config), so measuring does not change what the agents do. Driver: scripts/realm_eval.py;
runbook docs/runbooks/realm-of-agents.md § Evaluation (B253)."""
import contextlib
import time
import uuid

import router as gna
from agents import run_solo
from budget import free_only, is_free_only
from obs import current_extra_callbacks, extra_callbacks, log, set_session
from roster import BY_KEY, ROSTER, AgentSpec

try:   # the real base class at runtime; the tests stub langchain_core, so fall back to a plain class there
    from langchain_core.callbacks import BaseCallbackHandler
except ImportError:   # pragma: no cover - exercised only under the test stubs
    BaseCallbackHandler = object

__all__ = ["ARMS", "SINGLE", "RunCounter", "counting", "current_counters", "is_free_only", "run_arm"]

ARMS = ("realm", "routed", "single")

# The control arm's agent: every tool family any Realm agent uses (paid ones are dropped by free-only in fleet.py).
SINGLE = AgentSpec(
    "single", "Single agent", "Eval", "generalist",
    "One agent with every Realm tool and no team (B253 control arm).", "", lane="wl-default",
    tool_prefixes=tuple(sorted({p for a in ROSTER for p in a.tool_prefixes})))


class RunCounter(BaseCallbackHandler):
    """Tokens, model calls, tool calls and delegations across one request's whole delegation tree."""

    def __init__(self):
        super().__init__()
        self.input_tokens = self.output_tokens = self.llm_calls = 0
        self.tools_used: list[str] = []
        self.delegated_to: list[str] = []

    def on_llm_end(self, response, **kwargs):
        self.llm_calls += 1
        for gens in getattr(response, "generations", None) or []:
            for gen in gens:
                usage = getattr(getattr(gen, "message", None), "usage_metadata", None) or {}
                self.input_tokens += int(usage.get("input_tokens") or 0)
                self.output_tokens += int(usage.get("output_tokens") or 0)

    def on_tool_start(self, serialized, input_str, **kwargs):
        name = (serialized or {}).get("name") or kwargs.get("name") or "?"
        if name.startswith("delegate_to_"):
            self.delegated_to.append(name.removeprefix("delegate_to_"))
        else:
            self.tools_used.append(name)

    def as_dict(self) -> dict:
        return {"input_tokens": self.input_tokens, "output_tokens": self.output_tokens, "llm_calls": self.llm_calls,
                "tool_calls": len(self.tools_used), "delegations": len(self.delegated_to),
                "tools_used": list(self.tools_used), "delegated_to": list(self.delegated_to)}


@contextlib.contextmanager
def counting():
    """A fresh RunCounter on every run config built inside this block."""
    c = RunCounter()
    with extra_callbacks(c):
        yield c


def current_counters() -> tuple:
    return tuple(h for h in current_extra_callbacks() if isinstance(h, RunCounter))


async def run_arm(task: str, arm: str) -> dict:
    """Run `task` in `arm`, free-only, and return the answer with its measurements. Raises on an unknown arm or a
    failed run (the endpoint maps that to a 502, and the driver records the run as failed, never as missing)."""
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm!r}; one of {', '.join(ARMS)}")
    with free_only(), counting() as c:
        t0 = time.monotonic()
        routed_to = None
        if arm == "realm":
            routed_to, answer = await gna.dispatch(task)   # sets its own session
        else:
            set_session(str(uuid.uuid4()))
            if arm == "routed":
                routed_to = await gna.classify(task)
                answer = await run_solo(BY_KEY[routed_to], task)
            else:
                answer = await run_solo(SINGLE, task)
        seconds = round(time.monotonic() - t0, 2)
    log(f"eval {arm}: {seconds}s, {c.llm_calls} LLM calls, {len(c.tools_used)} tools, {len(c.delegated_to)} delegations")
    return {"arm": arm, "routed_to": routed_to, "answer": answer, "seconds": seconds, **c.as_dict()}
