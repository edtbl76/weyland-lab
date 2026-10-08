---
id: incident-enrich
title: The incident enrichment
category: Operations
description: For one firing alert, correlate recent logs and pod status and write a short incident summary, without taking any action.
terminal_condition: One summary is written for the alert (what is wrong, the likely cause, the current state), within at most six tool calls; no action is proposed or taken.
source: docs/runbooks/operator.md (Incident sweep (B45)), nodes/mother/lab/weyland-platform/services/weyland-operator/incidents.py
---

## Prompt

An alert is FIRING. Investigate and summarize. Do NOT propose or take any action.
Alert: {{alertname}} (severity {{severity}}) on {{target}}.

1. Open with the tool that reads live state for this alert's kind: pods, events or logs for a pod or job alert;
   Prometheus or node usage for a node, disk or spend alert. Do not open with the knowledge base.
2. Correlate the most recent logs and the pod or deployment status for the affected service. Use at most six tool
   calls in total.
3. If it is a synthetic or endpoint-down alert, say whether the pod is running versus the ingress, SSO or
   certificate path failing.

Write a concise incident summary: what is wrong, the likely cause, and the current state. If the evidence does not
show a cause, say "cause not shown" rather than guessing. Stop when the summary is written.
