# Flow: issue readiness — the check that replaced SpecBot (B190, 2026-10-06)

Before an issue is delegated to a coding agent, `scripts/issue-readiness.sh` checks it against the lab's written
implementation-ready standard (`AGENTS.md`; per kind, the Linear template's sections). Rules only — no model, under a
second. One comment per issue names what is missing. Why it is not an LLM score:
[concepts/issue-readiness.md](../concepts/issue-readiness.md). Runbook: [issue-readiness.md](../runbooks/issue-readiness.md).

```mermaid
sequenceDiagram
    participant T as Trigger (agent before delegating, or the lean-CI step)
    participant S as issue_readiness.py
    participant L as Linear API

    T->>S: EMA-249 or --sweep (open High, project Weyland Lab)
    S->>L: read issue (title, description, priority, labels)
    alt Linear unreachable, key missing, or a GraphQL error (429 backed off first)
        S-->>T: exit 2 - linear unavailable, never READY, no comment written
    else read
        S->>S: kind from labels or title - Backlog item, Bug, Spike or Bucket
        S->>S: each required section present with real content, not the template guidance or TBD
        S->>S: acceptance criteria hold a real checkbox or bullet, priority field set
        S->>L: create or update the ONE comment (READY, or the missing list) - unchanged result writes nothing
        S-->>T: exit 0 READY / 1 NOT READY with every missing item named
    end
```
