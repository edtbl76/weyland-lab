# Adopt Bifrost's Agent Gateway for the Realm (Relays stay out)

## Status

accepted

Date: 2026-11-19

Supersedes [ADR-0014](./0014-dont-adopt-bifrost-agent-gateway-or-relays.md)

## Context and Problem Statement

ADR-0014 kept the Realm of Agents off Bifrost's Agent Gateway: the Realm spoke A2A 0.3, the gateway accepts only A2A
v1, and the gateway seemed to add only per-caller keys and budgets. That verdict was written before the rest of
Bifrost's Agents section had been checked. When the owner reopened B249, the re-check found two things the existing
front door (Keycloak for people, a NetworkPolicy for programs, Langfuse traces) does not give:

* **Agent Logs:** every A2A call is logged with its caller's virtual key and its `contextId`, next to the MCP logs
  that the same conversation produced. One place shows who asked the Realm what, and which tools that answer used.
* **A per-caller grant:** an agent is granted to named virtual keys. A caller without the grant is refused before the
  Realm sees the call.

The Realm also had a gap: its A2A path always ran on the paid lane, whatever the caller asked for.

## Decision Drivers

* The owner runs the lab alone and wants the whole Agents surface exercised ("We want it all"), as long as it governs
  something real.
* The Realm's paid lane must stay closed unless a trusted caller asks for it.
* Everything Bifrost holds only in its database must be restorable from git.

## Considered Options

* Keep ADR-0014: the Realm's current front door only.
* Put the Realm behind the Agent Gateway for its programmatic callers (the operator first), with the Realm speaking A2A
  v1 next to 0.3.
* Also adopt Relays for the paid non-LLM APIs (TypeSafe, FRED, Clockify).

## Decision Outcome

Chosen option: **the Realm behind the Agent Gateway; Relays stay out** (owner, 2026-11-19: "Adopt. As part of B249.
Just do it. It's a single person show.").

* **The Realm speaks A2A v1** (`SendMessage`, a v1 card with `supportedInterfaces`) next to 0.3 (`message/send`, kept
  for the a2a-inspector). Both default to the free lane.
* **Paid needs two things:** the call asks for it (`metadata.allow_paid: true`) and it carries `X-Realm-Gateway-Token`.
  Bifrost adds that header to every call it forwards (runtime auth, from its own env). The 0.3 path and direct
  callers stay free-only. This closes the old always-paid gap.
* **Only the operator is granted** (virtual key `realm-operator`, `allow_by_default` off). Every granted key can reach
  the paid lane, so granting another caller is a new decision. `register_bifrost_realm_agent.py check` fails on any
  other grant.
* **One conversation, one id:** the A2A `contextId` becomes the Realm's dispatch session, and the Realm's MCP calls
  send it as `x-bf-session-id`, so Agent Logs and MCP logs line up.
* **Durable from git:** the registration lives only in Bifrost's `config.db`. The register script is its recorded
  definition and rebuilds it. The two secrets (the gateway token and the operator's key) are SealedSecrets.
* **Not used:** caller-IP restrictions (every caller is in-cluster), the complexity router, and push configurations
  (the Realm answers synchronously).
* **Relays: still no**, for ADR-0014's reasons. TypeSafe has one temporary consumer, prepaid credit and an alert, and
  its key is a SealedSecret in git. In Bifrost it would live only in the database.

### Consequences

* Good, because the operator's Realm calls are now granted per key, logged with their conversation id, and linked to
  the MCP calls they caused. The Realm's A2A path no longer spends by default.
* Neutral: the Realm keeps its direct `/route` path and its existing callers (Dagster, the a2a-inspector, Traefik).
  The operator falls back to it only when the gateway env is unset, never after a gateway error.
* Bad, because Bifrost is now on the operator's delegation path: when Bifrost is down, delegation fails instead of
  falling back. Bifrost's database also holds one more record to restore (the register script rebuilds it).

**Revisit when:** a second caller needs the paid lane (decide the grant), Bifrost's runtime auth or Agent Logs change
shape on an upgrade, or the operator's delegation needs to survive a Bifrost outage.

## More Information

* Backlog B249 (Linear EMA-349), which reopened the 2.5 re-evaluation and adopted the gateway.
* Evidence and the throwaway proof: [docs/concepts/bifrost-2-3-evaluation.md](../concepts/bifrost-2-3-evaluation.md)
  § 2.5 re-evaluation and § Agents section.
* Operation: [docs/runbooks/realm-of-agents.md](../runbooks/realm-of-agents.md) § Through Bifrost's Agent Gateway.
* Code: `services/realm-of-agents/a2a.py` (v1 and the paid check), `services/weyland-operator/realm.py`
  (`_via_gateway`), `scripts/register_bifrost_realm_agent.py`, `scripts/seal_realm_gateway.sh`.
