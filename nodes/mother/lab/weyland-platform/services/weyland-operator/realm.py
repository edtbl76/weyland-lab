"""Operator → Realm of Agents delegation (B17 A2A — the cross-service hop).

The operator is a single agent with read tools; the Realm is 24 specialist agents behind an A2A surface. This tool lets
the operator hand a specialist task to the Realm's dispatcher (Gná), which routes it to the best agent — that agent then
acts on its own tools or delegates to its team and returns a synthesized answer. Operator (agent) → Realm (agents) over
HTTP, in-mesh (mTLS) = the agent-to-agent boundary. Fail-soft: returns an error string, never raises (operator convention)."""
import os

import httpx
from langchain_core.tools import tool

REALM_URL = os.getenv("REALM_URL", "http://realm-of-agents.weyland.svc.cluster.local:8080")
REALM_TIMEOUT = float(os.getenv("REALM_TIMEOUT", "240"))


@tool
def delegate_to_realm(task: str) -> str:
    """Hand a specialist task to the Realm of Agents — 24 expert agents in five groups: Valhalla (engineering:
    architecture, coding, testing, devops, security, code review), Vanaheim (knowledge: consulting frameworks, AIDLC
    delivery, industry analysis, prompt engineering), Midgard (data & platform: observability/Grafana, SQL, data quality,
    graph/lineage, catalog), and the Well (research, eval-judging, content, safety). Gná routes the task to the right
    agent, which uses its own tools or delegates to its team, then returns one answer. Use this for work beyond your own
    read tools — e.g. 'audit the Grafana dashboards', 'review this SQL', 'apply a SWOT to X', 'trace the lineage of Y'.
    Returns which agent handled it and its answer."""
    try:
        r = httpx.post(f"{REALM_URL}/route", json={"message": task}, timeout=REALM_TIMEOUT)
        r.raise_for_status()
        d = r.json()
        return f"[handled by {d.get('god', '?')} · {d.get('role', '?')} · {d.get('realm', '?')}]\n{d.get('answer', '')}"
    except Exception as e:
        return f'{{"error": "delegate_to_realm failed: {e}"}}'


REALM_TOOLS = [delegate_to_realm]
