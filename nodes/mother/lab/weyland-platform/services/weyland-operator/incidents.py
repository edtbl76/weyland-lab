"""B45 — operator incident sweep (agent-in-the-loop, ENRICH-ONLY).

A background poll that runs strictly OFF the critical alert path. It READS the current firing alerts from Prometheus
(`ALERTS{alertstate="firing"}` — which already unifies everything: every firing PrometheusRule, INCLUDING the blackbox
synthetic `WeylandEndpointDown` for a down ingress and the guardrail/service down-alerts), dedups against Postgres, and
for each NEW incident invokes the operator agent to ENRICH it — correlate recent logs + pod status via the fleet MCP —
then posts a proactive Telegram summary ("tool-server down → OOMKilled 3m ago, last log X, pod restarting").

Hard B45 constraints:
  • ENRICH-ONLY — any action the agent proposes is DROPPED here (acts stay behind the Telegram confirm flow).
  • Never in the paging path — the operator only READS alert state from Prometheus; direct Kuma/Alertmanager→Telegram
    stays the pager. If this loop dies, paging is unaffected. That is the whole point.
"""
import asyncio
import os

import httpx
from prometheus_client import Counter

import agent
import session
import telegram

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus-operated.monitoring.svc.cluster.local:9090")
SWEEP_INTERVAL = int(os.getenv("INCIDENT_SWEEP_INTERVAL", "180"))    # seconds between sweeps
MAX_ENRICH_PER_SWEEP = int(os.getenv("INCIDENT_MAX_ENRICH", "5"))    # bound the agent runs in an alert storm
# Who receives the incident digest — a dedicated chat if set, else the first Telegram-allowlisted user.
_CHAT_ID = os.getenv("INCIDENT_CHAT_ID", "") or next(
    iter([s.strip() for s in os.getenv("TELEGRAM_ALLOWED_USERS", "").split(",") if s.strip()]), "")

_SWEEPS = Counter("operator_incident_sweeps_total", "Incident sweeps by outcome", ["outcome"])
_NOTIFIED = Counter("operator_incidents_notified_total", "Incidents enriched + notified")


def enabled() -> bool:
    """The sweep runs only when explicitly enabled AND Telegram + a target chat are configured."""
    return (os.getenv("INCIDENT_SWEEP_ENABLED", "false").lower() in ("1", "true", "yes")
            and telegram.configured() and bool(_CHAT_ID))


def _fingerprint(labels: dict) -> str:
    """Stable id for a firing alert: alertname + identity labels, so we notify once per firing episode."""
    return "|".join(f"{k}={labels.get(k, '')}" for k in ("alertname", "instance", "pod", "job", "namespace"))


def _who(labels: dict) -> str:
    return labels.get("instance") or labels.get("pod") or labels.get("job") or "?"


async def _firing(client: httpx.AsyncClient) -> list[dict]:
    """Query Prometheus for currently-firing alerts; return each alert's labels."""
    r = await client.get(f"{PROMETHEUS_URL}/api/v1/query",
                         params={"query": 'ALERTS{alertstate="firing"}'}, timeout=20)
    r.raise_for_status()
    return [res["metric"] for res in r.json().get("data", {}).get("result", [])]


def _investigation_prompt(labels: dict) -> str:
    return (
        f"An alert is FIRING — investigate and summarize. Do NOT propose or take any action.\n"
        f"Alert: {labels.get('alertname', '?')} (severity {labels.get('severity', '?')}) on {_who(labels)}.\n"
        f"Correlate the most recent logs and the pod/deployment status for the affected service, and give a concise "
        f"incident summary: what's wrong, the likely cause, and the current state. If it's a synthetic/endpoint down, "
        f"say whether the pod is running vs the ingress/SSO/cert path failing."
    )


async def _enrich_and_notify(client: httpx.AsyncClient, labels: dict) -> None:
    try:
        reply, _proposal = await agent.run(_investigation_prompt(labels), [])   # ENRICH-ONLY — proposal dropped
    except Exception as exc:
        reply = f"(enrichment failed: {exc})"
    await telegram.send_message(client, int(_CHAT_ID), f"🚨 {labels.get('alertname', '?')} — {_who(labels)}\n\n{reply}")
    _NOTIFIED.inc()


async def sweep_once(client: httpx.AsyncClient) -> None:
    firing = {_fingerprint(l): l for l in await _firing(client)}
    recorded = session.incidents_recorded()
    new_fps = [fp for fp in firing if fp not in recorded]
    for fp in new_fps[:MAX_ENRICH_PER_SWEEP]:          # cap per sweep; a storm overflow is picked up next sweep
        await _enrich_and_notify(client, firing[fp])
        session.incident_record(fp, firing[fp])        # record only AFTER a successful notify
    session.incidents_clear_resolved(set(firing))      # forget alerts no longer firing → a re-fire notifies again


async def sweep_loop() -> None:
    """Run until cancelled: every SWEEP_INTERVAL, read firing alerts → enrich+notify the new ones. Mirrors the
    telegram poll_loop's resilience — an error is logged, never wedges the loop."""
    async with httpx.AsyncClient() as client:
        while True:
            try:
                await sweep_once(client)
                _SWEEPS.labels("ok").inc()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                _SWEEPS.labels("error").inc()
                print(f"[incidents] sweep failed: {exc}", flush=True)
            await asyncio.sleep(SWEEP_INTERVAL)
