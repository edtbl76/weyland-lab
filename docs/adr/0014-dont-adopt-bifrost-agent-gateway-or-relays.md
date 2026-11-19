# Don't adopt Bifrost's Agent Gateway or Relays

## Status

accepted

Date: 2026-11-19

## Context and Problem Statement

Bifrost is the coding agents' MCP front door (`/mcp`, virtual keys). Since 2.3 it can also proxy A2A agents (the
Agent Gateway: a virtual key per caller, conversations logged), and since 2.4 it can relay calls to non-LLM APIs
(Relays: Bifrost holds the API's credential, callers send only their virtual key, every call logged and priced).
B212 (2026-10-19) rejected the Agent Gateway for the Realm on 2.3.1. B249 re-tested both features on 2.5.1 on a
throwaway instance, against the Realm's production image and a stand-in for the one paid non-LLM API an agent calls.

The lab already has a gateway per lane: LiteLLM (agentic LLM calls), the MLflow AI Gateway (chat, RAG, eval),
Bifrost (coding-agent MCP), weyland-mcp-gateway (governed MCP for people and the operator) and APISIX (HTTP APIs). The
Realm's front door is Keycloak forward-auth for people and a NetworkPolicy for programs.

## Decision Drivers

* Add a gateway feature only where it governs something the existing controls do not.
* Keep credentials and config reproducible from git where they are today.
* Keep each gateway in its lane.

## Considered Options

* Agent Gateway as the Realm's front door, with the Realm moved to A2A v1
* Keep the Realm's current front door (Keycloak for people, a NetworkPolicy naming the three in-cluster callers, Langfuse traces)
* Relays for the paid TypeSafe (Jev) API the operator's decision-model shadow calls, and for FRED and Clockify
* Keep those keys where they are

## Decision Outcome

Chosen options: keep the Realm's current front door, and keep the keys where they are (owner, 2026-11-19: "don't
adopt a gateway", then "yes, record it that way").

* **Agent Gateway:** blocker 2 from B212 (private destinations) is solved by configuration on 2.5.1
  (`a2a_private_allowlist`). Blocker 1 stands: the gateway accepts only A2A v1 cards and calls, and the Realm speaks
  0.3. A v1 stub proved the rest of the path works, so adopting would cost a small Realm change (a v1 card and
  `SendMessage`, about 150 lines) plus gateway config (External Client URL, allowlist, credential origins). But the
  Realm's programmatic callers are already restricted to three named in-cluster services, and every dispatch is
  traced in Langfuse, so the gateway would add only per-caller keys and budgets: too little for a sixth place to
  configure and watch.
* **Relays:** they work as described (the caller never holds the credential; refused calls are logged too). But the
  one real candidate, TypeSafe, has one consumer, is a temporary experiment (the B174 shadow), is already capped by
  prepaid credit and alerted (`OperatorDecideSpendObserved`), and its key is a SealedSecret in git. In Bifrost the
  credential would live only in Bifrost's database (it has no `config.json`), a step back for rebuilding the lab, and
  Bifrost would carry its only non-MCP traffic. FRED (a free API, called by a pipeline) and Clockify (a script) are
  weaker still.

### Consequences

* Good, because no new gateway surface, the Realm and the operator are unchanged, and the TypeSafe key stays
  GitOps-managed.
* Neutral: the evidence and the measured cost of A2A v1 are recorded, so a revisit starts from them.
* Bad, because the Realm's callers have no per-caller budget, and a paid API key stays in an LLM-driven agent's
  environment until the shadow experiment ends.

**Revisit when:** the Realm gets a caller outside the cluster, or enough callers that per-caller keys and budgets
matter (Agent Gateway); or several services, or untrusted agent code, call a paid non-LLM API with a stored key
(Relays).

## More Information

* Evidence: [docs/concepts/bifrost-2-3-evaluation.md](../concepts/bifrost-2-3-evaluation.md) § 2.5 re-evaluation
  (throwaway results on v2.5.1, 2026-11-19), and § Verdicts for B212's original test.
* Backlog B249 (Linear EMA-349), which re-tested B212 (2026-10-19).
* The gateway check: Bifrost `core/agent/manager.go`, `isStrictV1Interface` (an A2A v1 `supportedInterfaces` entry).
