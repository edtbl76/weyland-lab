# Flow — onboarding-completeness guard (B154 Phase 1a)

The coverage family proves a service is scraped / visualized / alerted / cataloged / registered. This
guard proves the surface none of them cover: a **deployed** service is **placed** in the single LikeC4
model. Concept: [application-catalog.md](../concepts/application-catalog.md); demo:
[onboarding-completeness.md](../demos/onboarding-completeness.md). The guard itself is repo tooling
(LikeC4 N/A); the 3 elements it forced into the model on first run are the drift it found.

## Per-service resolution (declared → matched → placed?)

```mermaid
flowchart TD
    A["each applications.yaml entry"] --> D{deployed: true?}
    D -->|false| SKIP["skip — not a cluster workload (SaaS/IDE, code-review group)"]
    D -->|true| O{explicit likec4: id?}
    O -->|yes| OE{id exists in the model?}
    OE -->|yes| OK1["PLACED"]
    OE -->|no| BAD1["UNPLACED — declared likec4:&lt;id&gt; not in model"]
    O -->|no| M{"normalized key/name matches a<br/>model element? (kind-agnostic:<br/>component/gateway/store/node)"}
    M -->|yes| OK2["PLACED"]
    M -->|no| BAD2["UNPLACED — add the element or declare likec4:"]
```

## Fail-closed exit contract

```mermaid
flowchart TD
    S[run] --> R{registry readable + has applications?}
    R -->|no| E2A["exit 2 — CANNOT RUN (never a clean estate on a failed read)"]
    R -->|yes| L{model readable + elements parsed?}
    L -->|no| E2B["exit 2 — CANNOT RUN (never 'all unplaced' on a parse failure)"]
    L -->|yes| C{every deployed service placed?}
    C -->|yes| E0["exit 0 — all N placed"]
    C -->|no| E1["exit 1 — name each unplaced service + the fix"]
```

- **Declarative contract, not fuzzy guessing:** `deployed: true|false` is declared per service; placement
  resolves by an explicit `likec4: <id>` (authoritative — for a subsumed/renamed element) else a
  normalized key/name match. A new service that matches nothing is nudged to add the element or declare
  the id — which is exactly the onboarding step that was silently skippable before.
- **Fail closed:** exit 1 = a defect (an unplaced deployed service, named); exit 2 = the guard could not
  run (registry/model unreadable or empty) — never conflated with a clean estate, the coverage-guard rule.
- **What it caught on first run:** `weyland-agent`, `port-k8s-exporter`, `promptfoo` were deployed but
  absent from the model; all three were added (fix-don't-file) so the live invariant now holds (59/59).
