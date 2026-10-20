# Flow — Anthropic model deprecations (B223)

Two checks answer "does anything here use a model Anthropic is retiring?", both from one manifest
(`scripts/anthropic-models.json`, copied from Anthropic's deprecations page) and one script (`scripts/model_lifecycle.py`).
The **repo guard** runs in CI over what git holds. The **live check** runs nightly at 03:55 NY over what the gateways
hold in their own databases. Operate: [runbooks/model-deprecations.md](../runbooks/model-deprecations.md).

## Repo guard (every CI build)

```mermaid
sequenceDiagram
    participant CI as Woodpecker repo-guards
    participant G as check-model-deprecations.sh
    participant M as anthropic-models.json
    participant T as repo tree (config + code)
    CI->>G: bash scripts/check-model-deprecations.sh
    G->>M: load + validate every row
    alt manifest missing or malformed
        G-->>CI: exit 2, CANNOT CHECK
    else manifest valid
        G->>T: walk files, skip docs, history, tests, .claude, notebook outputs
        T-->>G: every Anthropic model ID with file and line
        alt no files scanned
            G-->>CI: exit 2, scanning nothing is not clean
        else a retired ID, or retiring within 30 days
            G-->>CI: exit 1, FAIL path:line, id, replacement
        else deprecated with time left, or not in the manifest
            G-->>CI: exit 0 with WARN lines
        else all active
            G-->>CI: exit 0, OK with reference and file counts
        end
    end
```

## Live check (anthropic-model-watch, 03:55 NY)

```mermaid
sequenceDiagram
    participant J as anthropic-model-watch Job
    participant ML as MLflow AI Gateway
    participant B as Bifrost admin API
    participant A as Anthropic GET v1 models
    participant K as kube-state-metrics rules
    J->>ML: model-definitions list (admitted by the MLflow front-door policy)
    ML-->>J: model definitions, the anthropic ones kept
    J->>B: anthropic keys + virtual keys (setup token)
    B-->>J: model lists, a star names no model
    J->>A: list models with Bifrost's key, every page
    A-->>J: the IDs that key can still call
    alt a source unreadable, or the API lists nothing
        J-->>K: exit 2, Job fails, ScheduledJobFailed pages
    else every source read
        loop each Anthropic ID the gateways name
            J->>J: classify against the manifest, and is it offered
        end
        alt retired, retiring within 30 days, or not offered
            J-->>K: exit 1, Job fails, ScheduledJobFailed pages
        else all active and offered
            J-->>J: exit 0, Job complete
        end
    end
```
