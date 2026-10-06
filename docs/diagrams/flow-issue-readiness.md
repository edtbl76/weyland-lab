# Flow: issue readiness — the lab's scorer for Linear issues (B190, 2026-10-06)

Is a Linear issue ready to hand to a coding agent? `scripts/issue-readiness.sh` answers with 8 dimension scores and a
total (threshold 80), and keeps ONE comment on the issue current. Rules decide what the text can settle; a local judge
(gpt-oss:20b through LiteLLM `wl-judge-oss`) scores the rest, three times, and must quote the issue for every score of
50+. The lean-CI sweep re-scores only issues whose content changed. Runbook:
[issue-readiness.md](../runbooks/issue-readiness.md).

```mermaid
sequenceDiagram
    participant T as Trigger (CLI or lean-CI step)
    participant S as issue_readiness.py
    participant L as Linear API
    participant G as LiteLLM wl-judge-oss
    participant O as Ollama gpt-oss 20b-judge (rogueone GPU)

    T->>S: EMA-249 or --sweep
    S->>L: read issue (title, description, priority, labels, links)
    alt sweep and the issue digest matches its last comment
        S-->>T: unchanged since last score (no model call)
    else score it
        S->>S: rules - no acceptance criteria, edge cases, repro, dependencies, priority -> fixed score or cap
        loop 3 votes
            S->>G: rubric + issue, temperature 0, JSON only
            G->>O: chat (16K window)
            O-->>G: scores + verbatim quotes
            G-->>S: reply + x-litellm headers (backend, fallbacks)
            S->>S: validate - every dimension, integer 0-100, one retry
            S->>S: quote check - a 50+ score whose quote is not in the issue is capped at 40
        end
        S->>S: median per dimension, rules applied, total = rounded mean
        S->>L: create or update the ONE comment (marker + digest + model + rubric version)
        S-->>T: exit 0 READY / 1 NOT READY
    end
    alt judge or Linear unreachable, or the reply unusable after retry
        S-->>T: exit 2 - scorer unavailable or invalid, never a guessed score
    end
    Note over G,O: HTTP 429 is backed off and retried, then exit 2 - never a partial score
```
