"""Operator → Realm of Agents delegation (B17 A2A — the cross-service hop).

The operator is a single agent with read tools; the Realm is 24 specialist agents behind an A2A surface. This tool lets
the operator hand a specialist task to the Realm's dispatcher (Gná), which routes it to the best agent — that agent then
acts on its own tools or delegates to its team and returns a synthesized answer. Fail-soft: returns an error string,
never raises (operator convention).

Two paths (B249, 2026-11-19):
  * **Through Bifrost's Agent Gateway** (REALM_GATEWAY_URL and REALM_GATEWAY_VK set): A2A v1 `SendMessage` with the
    operator's own virtual key, so every delegation is a governed, logged conversation in Bifrost's Agent Logs. The
    Realm is granted to this key only, and `allow_paid` rides in the message metadata; the Realm honours it only with
    the token Bifrost adds on calls it forwards. A gateway failure is reported, never retried on the direct path: a
    broken gateway must not quietly bypass the governed one.
  * **Direct** (either unset): the Realm's REST `/route`, in-mesh, as before.
"""
import os
import uuid

import httpx
from langchain_core.tools import tool

REALM_URL = os.getenv("REALM_URL", "http://realm-of-agents.weyland.svc.cluster.local:8080")
REALM_TIMEOUT = float(os.getenv("REALM_TIMEOUT", "240"))
REALM_GATEWAY_URL = os.getenv("REALM_GATEWAY_URL", "")   # Bifrost .../agents/a2a/realm/json-rpc
REALM_GATEWAY_VK = os.getenv("REALM_GATEWAY_VK", "")     # the operator's Bifrost virtual key (granted the Realm)


def _handled(who: dict, answer: str) -> str:
    return f"[handled by {who.get('god', '?')} · {who.get('role', '?')} · {who.get('realm', '?')}]\n{answer}"


def _via_gateway(task: str) -> str:
    body = {"jsonrpc": "2.0", "id": uuid.uuid4().hex, "method": "SendMessage",
            "params": {"message": {"messageId": uuid.uuid4().hex, "role": "ROLE_USER", "parts": [{"text": task}],
                                   "metadata": {"allow_paid": True}}}}
    r = httpx.post(REALM_GATEWAY_URL, json=body, timeout=REALM_TIMEOUT,
                   headers={"x-bf-vk": REALM_GATEWAY_VK, "A2A-Version": "1.0"})
    r.raise_for_status()
    d = r.json()
    if d.get("error"):
        raise RuntimeError(f"gateway: {d['error'].get('message', d['error'])}")
    msg = (d.get("result") or {}).get("message") or {}
    answer = " ".join(p["text"] for p in msg.get("parts") or [] if isinstance(p, dict) and isinstance(p.get("text"), str))
    if not answer.strip():
        raise RuntimeError("gateway: the reply had no text")
    return _handled(msg.get("metadata") or {}, answer)


def _direct(task: str) -> str:
    # B209: the Realm defaults to the free lane; this tool exists only on the paid brain, so it asks for paid.
    r = httpx.post(f"{REALM_URL}/route", json={"message": task, "allow_paid": True}, timeout=REALM_TIMEOUT)
    r.raise_for_status()
    d = r.json()
    return _handled(d, d.get("answer", ""))


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
        return _via_gateway(task) if (REALM_GATEWAY_URL and REALM_GATEWAY_VK) else _direct(task)
    except Exception as e:
        return f'{{"error": "delegate_to_realm failed: {e}"}}'


REALM_TOOLS = [delegate_to_realm]
