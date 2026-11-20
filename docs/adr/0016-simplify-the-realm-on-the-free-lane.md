# Simplify the Realm of Agents on the free lane

## Status

accepted

Date: 2026-11-20

## Context and Problem Statement

The Realm of Agents (B17) routes each task through Gná to one of 23 agents, and a lead hands sub-tasks to its members.
B253 measured whether that shape beats simpler ones on the same model and tools: 33 tasks, 3 arms, 3 runs each, on the
free local lane (`qwen2.5:7b-operator`), judged blind by `wl-judge-oss`. Delegation added nothing for 3.6 times the
tokens; the specialists scored about half as well as one generalist agent on the tasks Gná routed correctly; Gná routed
58% of tasks correctly and picked herself in 18 of 99 dispatches; the generalist failed on pure-reasoning tasks because
about 26,000 tokens of tool schemas fill every prompt.

## Decision Drivers

* Every automatic caller (the ship transaction, free A2A calls, the eval itself) runs on the free lane.
* Spend tokens and latency only where they buy answer quality.
* Change the production paid path only on evidence from that path.

## Considered Options

* Keep the Realm as it is.
* Simplify: treat routing plus delegation as not earning its cost on the free lane, fix Gná's self-routing, and move the
  generalist's context-bloat problem to tool selection (B255).
* Replace the Realm with one generalist agent now.
* Spend about $5-6 on a paid (Haiku) sample before deciding.

## Decision Outcome

Chosen option: **simplify** (owner, 2026-11-20: "I'm fine w/ that", after the results; no paid sample: nothing in this
decision changes the paid path).

* Gná is left off her own menu (done in B253; a reply naming her fails safe to Odin).
* On the free lane, a single generalist is the better shape for tool tasks; its weakness (tool-schema bloat) is B255's
  to fix with tool retrieval or subsetting, judged on B253's task set.
* The Realm keeps its shape, A2A front door, cards, console and the operator's paid path. Dropping the leads' delegation
  mandate, or replacing specialists with one agent, is a follow-up decision that this ADR does not take.

### Consequences

* Good, because the evaluation is reproducible (`scripts/realm-eval.sh`, `eval_sets/realm.json`, results in
  `eval/realm-b253/`), so B254's framework bake-off and B255's tool-selection work start from a measured baseline.
* Good, because Gná no longer answers tasks herself, and free-only requests can no longer spend on Perplexity.
* Neutral: the Realm runs unchanged otherwise; the evidence says its delegation is overhead on the free lane.
* Bad, because the paid lane is unmeasured, so a verdict about the operator's Haiku path would need its own sample.

**Revisit when:** someone proposes changing the operator's paid Realm path (run the paid sample first), B255 lands tool
retrieval (re-run the single arm), or the free lane's model changes.

## More Information

* Evidence: [docs/concepts/realm-evaluation.md](../concepts/realm-evaluation.md) (method, results, paired analysis,
  limits). Runbook: [realm-of-agents.md § Evaluation](../runbooks/realm-of-agents.md).
* Backlog B253 (Linear EMA-354); follow-ups B254 (framework bake-off, reuses the task set) and B255 (context engineering).
