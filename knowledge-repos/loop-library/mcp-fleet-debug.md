---
id: mcp-fleet-debug
title: The MCP fleet debug
category: Operations
description: When agents lose MCP tools, find which server or layer is broken by smoking each one directly, prove the layer, and fix it.
terminal_condition: Every fleet server returns a non-empty tools/list through the smoke, or the failing layer (server, gateway, auth, network) is proven by a direct test and the fix is named or applied.
source: docs/runbooks/mcp-fleet.md (Verify — the reusable MCP smoke; Connectivity notes; Deploy gotchas)
---

## Prompt

Agents report missing or failing MCP tools ({{symptom}}). Find the broken layer.

1. List the fleet's servers from `docs/runbooks/mcp-fleet.md` § "The 6 servers".
2. Smoke each server directly with the reusable smoke in that runbook (initialize, then tools/list), from the guard
   pod. Note which servers answer and with how many tools. SSE servers use the threaded reader the runbook gives.
3. A server that answers directly but not through the gateway or compositor is a gateway or auth problem; one that
   does not answer directly is the server itself. Prove the layer with one direct test before changing anything.
4. Check the runbook's Deploy gotchas for the failing server before inventing a fix.

Stop when the terminal condition holds. Report each server's tool count, the proven failing layer, and the fix.
