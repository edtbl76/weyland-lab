"""morning_run.py — the B243 morning remediation's decisions, one item at a time (2026-11-24).

Pure orchestration: everything that reaches out is injected through `deps` (triage by a model, the allowlisted action,
its verification, a fix attempt, the history of earlier nights), so each rule is tested without a model or a system
(scripts/tests/test_morning_run.py). Per item:
  1. caused by an agent (e.g. a run the morning runner itself re-executed)  -> reported separately, never acted on;
  2. attempted on an earlier night                                          -> "recurring, not retried", with history;
  3. triage (the model) -> {classification, diagnosis, action: {id, params} | null, fix: bool};
  4. an action: ONE call through the allowlist executor; reported fixed only if verification passed;
     a fix:      a local auto-fix/<date>-<slug> branch with the full gate suite; "ready" only if the gates passed;
     neither:    "not fixed", with the diagnosis and what a person must decide.
A triage that fails or times out is reported and the remaining items still run. The report never claims more than
was verified, and a night with an unreadable source is never "quiet".
"""
import dataclasses
import re

FIXED = "fixed by an allowlisted retry"
READY = "fix branch ready"
NOT_FIXED = "not fixed"
RECURRING = "recurring, not retried"
AGENT = "caused by an agent"


class ActionRefused(Exception):
    """The allowlist refused the action (raised by the action dependency)."""


@dataclasses.dataclass
class Outcome:
    item: object
    result: str
    detail: str
    classification: str = ""
    diagnosis: str = ""
    action: str = ""


@dataclasses.dataclass
class Report:
    date: str
    status: dict
    outcomes: list

    @property
    def quiet(self) -> bool:
        return not self.outcomes and all(v.startswith("checked") for v in self.status.values())


def slug(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-")[:48]


def _earlier(history: dict, key: str, date: str) -> list:
    return [h for h in history.get(key, []) if h.get("date") != date]


def _act(item, decision, deps) -> tuple:
    action = decision["action"]
    try:
        ok, detail = deps.act(action["id"], action.get("params") or {})
    except ActionRefused as exc:
        return NOT_FIXED, f"the action was refused: {exc}"
    if not ok:
        return NOT_FIXED, f"{action['id']} did not succeed: {detail}"
    verified, evidence = deps.verify(item, action["id"], detail)
    return (FIXED, f"{action['id']}: {detail}; {evidence}") if verified else \
        (NOT_FIXED, f"{action['id']} ran ({detail}) but verification failed: {evidence}")


def _fix(item, decision, deps) -> tuple:
    res = deps.fix(item, decision)
    branch, gates = res.get("branch", "?"), res.get("gates", "not run")
    if gates == "passed":
        return READY, f"branch {branch} (local, not pushed); full gate suite passed"
    return NOT_FIXED, f"fix attempted on {branch} but the gates did not pass: {gates}"


def _one(item, deps, date: str) -> Outcome:
    if getattr(item, "agent_caused", False):
        return Outcome(item, AGENT, "started by the morning runner itself; not a real fault")
    earlier = _earlier(deps.history, item.key, date)
    if earlier:
        seen = "; ".join(f"{h['date']}: {h['outcome']}" for h in earlier[-3:])
        return Outcome(item, RECURRING, f"seen on earlier nights ({seen}); needs a person, not another retry")
    try:
        decision = deps.triage(item)
    except Exception as exc:   # a stuck or failed triage is reported; the night goes on
        return Outcome(item, NOT_FIXED, f"triage stopped: {type(exc).__name__}: {exc}")
    common = {"classification": decision.get("classification", ""), "diagnosis": decision.get("diagnosis", "")}
    if decision.get("action"):
        outcome, detail = _act(item, decision, deps)
        return Outcome(item, outcome, detail, action=decision["action"]["id"], **common)
    if decision.get("fix"):
        outcome, detail = _fix(item, decision, deps)
        return Outcome(item, outcome, detail, action="code fix", **common)
    detail = "no safe action; a person decides (see the diagnosis)" if common["diagnosis"] else \
        "no safe action, and the triage gave no diagnosis"
    return Outcome(item, NOT_FIXED, detail, **common)


def run(failures: list, status: dict, deps, *, date: str) -> Report:
    return Report(date, dict(status), [_one(item, deps, date) for item in failures])


def render(report: Report) -> str:
    """The morning summary (Slack mrkdwn). Evidence is already scrubbed by the collector."""
    lines = [f"*Morning remediation, {report.date}*"]
    unchecked = {k: v for k, v in report.status.items() if not v.startswith("checked")}
    if report.quiet:
        lines.append("Quiet night: every source checked, nothing broke.")
    for name, why in unchecked.items():
        lines.append(f":warning: {name}: {why}")
    real = [o for o in report.outcomes if o.result != AGENT]
    caused = [o for o in report.outcomes if o.result == AGENT]
    for o in real:
        lines.append(f"\n*{o.item.title}* ({o.item.source}) — *{o.result}*")
        if o.item.evidence:
            lines.append(f"> evidence: {o.item.evidence.splitlines()[-1][:300]}")
        if o.diagnosis:
            lines.append(f"> diagnosis ({o.classification}): {o.diagnosis[:400]}")
        if o.action:
            lines.append(f"> action: {o.action}")
        lines.append(f"> outcome: {o.detail[:500]}")
        if o.item.link:
            lines.append(f"> {o.item.link}")
    if caused:
        lines.append("\n*Caused by an agent* (not real faults): " + "; ".join(o.item.title for o in caused))
    return "\n".join(lines)
