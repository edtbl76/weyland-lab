# Shared context for many humans and agents: layers in one store, with governed writes

## Status

proposed

Date: 2026-11-23

## Context and Problem Statement

The lab's shared memory (B182: Markdown notes served by Basic Memory) works for one human and their agents. With
several agents side by side (Herdr, ADR-0018) and possibly a second human, it breaks: reads carry identity through the
governed MCP gateway, but writes do not (every coding agent shares one Bifrost key, Claude Code writes the files
directly), so no note records who wrote it; the store has one flat scope; an edit of the same note is last-writer-wins;
stale facts accumulate. B256 wrote three scenarios, inventoried what exists, surveyed 15 approaches from primary
sources, and proved a walking skeleton. What structure should shared context take?

## Decision Drivers

* Build on B182: one store of plain Markdown, Basic Memory 0.23.2, the governed gateway; do not replace Basic Memory,
  Linear or git.
* $0, self-hosted; human-readable notes; fail closed (unreachable is not "no memory"); secrets never enter memory.
* Rules enforced in code at one point, not in prose.

## Considered Options

* **Layers in the one store, with writes through the governed gateway** (identity-checked rights, provenance stamped by
  the gateway, write classes, supersede-not-delete, a hand-off note per task).
* **Basic Memory Teams / Cloud** (roles, file history, a review queue): paid cloud ($15/month), per-project roles only.
* **A new store with scopes or temporal facts** (Mem0, Graphiti, Letta): a second copy of the notes, plus a database
  and LLM extraction.
* **CRDT documents** (Automerge, Yjs): merge without loss, but not plain Markdown, and one-fact-per-note rarely
  conflicts.
* **Per-harness namespaces with prose rules only** (keep today's write paths, add directories): no identity, so no
  provenance or enforcement.

## Decision Outcome

Chosen option: **layers in the one store, with writes through the governed gateway**. The design and the skeleton were
approved by the owner on 2026-11-23 ("yes"). The design is
[docs/design/shared-context-design.md](../design/shared-context-design.md):

* Layers: lab rules (git), project memory (the store root), `task/<item>/`, `person/<name>/` (private to that person and
  their agents); harness session context stays per harness.
* Writes go through the memory compositor behind `/mcp-memory`; the identity is what the gateway set from a validated
  Keycloak token; a rights table in code decides per identity and layer; refusals name the rule.
* Provenance (`created_by`, `updated_by`, `author_kind`, `on_behalf_of`, `source`, times) is stamped by the gateway, never
  by the caller. Write classes: create fails if the note exists, append always works, replace needs the version read.
* Stale facts are superseded, never deleted; review dates; a task layer is reviewed at item close.

**Proved by the walking skeleton** (live 2026-11-23, `git-a2b44536`): through the real gateway with the operator's own
token, a task-layer write was accepted and stamped `agent:weyland-operator`; project-memory and person-layer writes were
refused with the rule named; Basic Memory's own write tool stayed blocked; the gateway and compositor audit lines agree.
51 unit and manifest tests; a security review's path-traversal finding on the read tool was fixed before shipping.

### Consequences

* Good, because every governed write says who wrote it, human or agent, and for whom, and a forbidden or stale write
  never reaches the store.
* Good, because secrets are now refused at write time on this path (B182 could only flag them after the fact).
* Bad, because today's writers (the shared Bifrost key, Claude Code's direct file writes) are not on this path yet:
  their notes carry no provenance until agents get their own Keycloak clients and move over.
* Bad, because Basic Memory's own read tools do not yet apply the person layer's read rule (only the governed read does).
* Neutral: the governed tools run on the memory compositor only (`GOVERNED_WRITE=1`), guarded by tests that fail if the
  fleet compositor gets the switch or anything but the gateway can reach the memory compositor.

**Revisit when:** a second human is onboarded, an agent client is added, or a store with built-in identity and history
becomes free and self-hosted.

## More Information

* Design, scenarios, inventory, survey and skeleton evidence: [docs/design/shared-context-design.md](../design/shared-context-design.md).
* Runbook: [docs/runbooks/shared-agent-memory.md § Governed writes](../runbooks/shared-agent-memory.md). B182's design:
  [docs/design/shared-agent-memory-design.md](../design/shared-agent-memory-design.md).
* Backlog B256 (Linear EMA-357). Builds on B182 (EMA-240), B255 (ADR-0017), B257 (ADR-0018).
