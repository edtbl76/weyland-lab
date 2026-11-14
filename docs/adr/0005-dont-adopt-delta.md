# Don't adopt Delta (delta.dev)

## Status

accepted

Date: 2026-10-29

## Context and Problem Statement

Delta, a collaborative agent workspace from the Zed team (beta), was evaluated against Emdash, the lab's parallel-agent supervisor.

## Decision Drivers

* Unattended runs.
* Reach to the lab's MCP servers (Bifrost `/mcp` authenticates with a bearer token).
* Code and keys stay on the lab's machines.

## Considered Options

* Keep Emdash
* Delta

## Decision Outcome

Chosen option: Keep Emdash (owner, 2026-10-29: "it's a no-go"), because Delta has no unattended runs, cannot reach token-authenticated MCP servers, and keeps repos, commits and provider keys on its own backend with telemetry that cannot be disabled.

### Consequences

* Good, because the unattended conveyor (B179) keeps working as built.
* Neutral: revisit only if Delta adds local mode and headless runs.

## More Information

Concept: [software-factory.md](../concepts/software-factory.md) § Delta. Backlog B210.
