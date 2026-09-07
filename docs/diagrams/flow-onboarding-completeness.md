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

## The scaffolder — landing paved instead of auditing into compliance (Phase 1b)

`scripts/onboard-service.sh` is the other half of the paved road: it writes the two surfaces the guard
checks, from one command, so a new service starts onboarded-complete.

```mermaid
flowchart TD
    I["onboard-service.sh --key --name --group --zone [--kind …]"] --> V{args valid?<br/>kebab key · known group/kind/zone}
    V -->|no| R1["exit 1 — refuse, name the bad arg"]
    V -->|yes| DUP{key in registry OR<br/>id already in model?}
    DUP -->|yes| R2["exit 1 — refuse to duplicate"]
    DUP -->|no| DR{--dry-run?}
    DR -->|yes| P["print both additions, write nothing (exit 0)"]
    DR -->|no| W["append registry entry (deployed:true, likec4:&lt;camelId&gt;)<br/>+ insert element as first in the zone"]
    W --> G{check-onboarding-completeness passes?}
    G -->|yes| OK["exit 0 — onboarded (element placed but UNWIRED — wire edges by hand)"]
    G -->|no| R3["exit 2 — scaffold did not verify; inspect the two files"]
```

- **Id = camelCase(key)**, written as an explicit `likec4:` on the entry AND as the element id, so the
  guard resolves it two ways. The tool refuses a duplicate key or id, validates the group/kind/zone
  against the real files, and `--dry-run` shows exactly what it would write.
- **Honest boundary:** it *places* the element but never invents relationships — wiring edges is a human
  judgement the scaffold leaves as a stated follow-up, not a guess.
