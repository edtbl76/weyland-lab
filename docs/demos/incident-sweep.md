# Demo — Operator incident sweep (`weyland-operator`, B45)

The operator **enriches** firing incidents instead of just re-paging them. A 180 s loop reads the currently-firing
Prometheus alerts **off the critical alert path**, dedups against Postgres, and for each *new* incident runs the agent
to correlate recent logs + pod status via the MCP fleet → posts a proactive Telegram digest. **Enrich-only** — it never
acts, and it never sits in the paging path (direct Kuma/Alertmanager→Telegram stays the pager). Validated 2026-08-04 —
the first real sweep surfaced a **12-day postgres-backup outage** buried under 8 noise alerts.

Grounded in [runbooks/operator.md](../runbooks/operator.md) (Incident sweep section). Sequence:
[diagrams/flow-incident-sweep.md](../diagrams/flow-incident-sweep.md).

## Sequence diagram

See [diagrams/flow-incident-sweep.md](../diagrams/flow-incident-sweep.md) — the paging path (independent) vs. the
enrichment path (ALERTS → dedup → enrich → Telegram digest).

## Prerequisites

- **mother** — `weyland-operator` (`INCIDENT_SWEEP_ENABLED=true`, a Telegram bot + `INCIDENT_CHAT_ID`/allowlist),
  `weyland-postgres` (the `operator_incidents` dedup table), Prometheus (`prometheus-operated.monitoring.svc:9090`),
  the MCP fleet (loki/k8s, for enrichment).
- Read-only demo — the sweep only *reads* alert state, *enriches*, and *notifies*; it writes only dedup rows.

## Walkthrough — the sweep IS the test

**1. The sweep is running.** Confirm the loop started (once, at pod boot):
```
[mother] kubectl -n weyland logs deploy/weyland-operator | grep -iE "incident sweep started|\[incidents\]"
```
→ `[incidents] B45 incident sweep started`.

**2. What's firing right now** (what the sweep reads — the same query, off the critical path):
```
[mother] kubectl -n weyland exec deploy/weyland-operator -- python -c "import httpx; r=httpx.get('http://prometheus-operated.monitoring.svc.cluster.local:9090/api/v1/query', params={'query':'ALERTS{alertstate=\"firing\"}'}, timeout=20).json(); print([ (m['metric'].get('alertname'), m['metric'].get('severity')) for m in r['data']['result'] ])"
```
→ the firing alerts; the sweep drops `severity=none` (Watchdog/InfoInhibitor) + `INCIDENT_SKIP_ALERTS`
(LiteLLMEgressEnabled) and enriches the rest.

**3. The enrichment digest (UI — the headline).** A *new* incident produces a proactive Telegram message like:
```
🚨 WeylandEndpointDown — grafana.weyland.lab

The blackbox probe for grafana.weyland.lab is failing. The pod is Running (1/1) — the failure is at the
ingress/SSO path, not the app: last Loki lines show forward-auth 302→Keycloak with no cookie. Likely a
stale session, not an outage. Current state: probe red, pod healthy.
```
Not a raw "X is down" — *what's wrong, the likely cause, the current state*, correlated from logs + pod status.

**4. Dedup — notify once per firing episode.** The recorded incidents (one row per still-firing episode):
```
[mother] kubectl -n weyland exec deploy/weyland-postgres -- psql -U weyland -d weyland -c "SELECT alertname, instance, notified_at FROM operator_incidents ORDER BY notified_at DESC;"
```
A second sweep does **not** re-notify these; when an alert stops firing its row is cleared, so a later re-fire notifies
again.

**5. UAT — eyes on Telegram.** Open the Weyland Alerts chat and visually confirm: the digest **rendered**, names the
**right** service, and reads as an *enrichment* (cause + state), not a bare ping. The paging messages (direct
Kuma/Alertmanager) are a **separate** bot — confirm the sweep digests come from the operator bot, not the pager.

**6. Metrics.**
```
[mother] kubectl -n weyland exec deploy/weyland-operator -- python -c "import urllib.request; print([l for l in urllib.request.urlopen('http://localhost:8080/metrics').read().decode().splitlines() if l.startswith(('operator_incident_sweeps_total','operator_incidents_notified_total'))])"
```
→ `operator_incident_sweeps_total{outcome="ok"}` climbing every 180 s; `operator_incidents_notified_total` = the count
enriched.

**7. The sweep spends nothing (2026-10-02).** Confirm the switch is off, the sweep's brain has no `delegate_to_realm`
(the Realm runs on paid Haiku) while the chat brain keeps it, and how sweeps are ending:
```
[mother] kubectl -n weyland exec deploy/weyland-operator -c weyland-operator -- python -c "import os, urllib.request, incidents, agent; t=lambda a: 'delegate_to_realm' in a.get_graph().nodes['tools'].data.tools_by_name; print('ALLOW_PAID', os.environ.get('INCIDENT_SWEEP_ALLOW_PAID'), incidents.SWEEP_ALLOW_PAID); print('sweep realm', t(agent._unpaid_agent), '| chat realm', t(agent._local_agent)); print([l for l in urllib.request.urlopen('http://localhost:8080/metrics').read().decode().splitlines() if l.startswith(('operator_incident_sweeps_total','operator_brain_selected_total'))])" 2>&1 | grep -vE '^\[(fleet|agent|langfuse)\]'
```
→ RUN 2026-10-02 on `git-9cb55524`: `ALLOW_PAID false False` · `sweep realm False | chat realm True` ·
`operator_incident_sweeps_total{outcome="ok"} 75.0`. During an eval, expect `outcome="deferred"` and
`operator_brain_selected_total{brain="none"}` instead of any `brain="haiku"`. To give sweeps the paid path back:
[runbooks/operator.md](../runbooks/operator.md) § Sweeps spend nothing by default.

## Expected result

- Every 180 s the sweep reads firing alerts, enriches each **new** real incident, and Telegram-digests it — **once**.
- Noise (`severity=none` + skip-list) is never enriched; the digest stays real-signal-only.
- `operator_incidents` holds one row per firing episode; `operator_incident_sweeps_total{outcome="ok"}` increments each sweep.
- Killing the operator stops enrichment but **not** paging — `WeylandOperatorDown` fires, the pager is unaffected.
- A sweep never spends money by default: no Haiku failover, no Realm; while the local model is busy it defers
  (`outcome="deferred"`) and retries, and `WeylandOperatorSweepDeferred` fires only after 6 h of that.

## Cleanup / teardown

Read-only — the sweep creates no lab state beyond dedup rows and Telegram messages. To reset the dedup table (forces
re-notification of currently-firing incidents on the next sweep):

```
[mother] kubectl -n weyland exec deploy/weyland-postgres -- psql -U weyland -d weyland -c "DELETE FROM operator_incidents;"
```
