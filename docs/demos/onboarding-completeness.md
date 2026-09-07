# Demo — onboarding-completeness guard (B154 Phase 1a)

The estate proves a service is scraped / visualized / alerted / cataloged / registered, but nothing
proved a **deployed** service is **placed** in the single LikeC4 model — the exact drift the DoD flags,
which bit the `image-provenance` CronJob on 2026-09-07 (its LikeC4 node was missing, caught only in a
manual re-audit). This guard closes that surface. Concept:
[application-catalog.md](../concepts/application-catalog.md); flow:
[flow-onboarding-completeness.md](../diagrams/flow-onboarding-completeness.md).

This is repo tooling — no UI. The **CLI walkthrough IS the demo**, run in the CI's exact image, with the
**negative cases** (each failure shown with its exit code).

## CLI walkthrough (RUN 2026-09-07)

**1. The live invariant — every deployed service is placed:**

```
bash scripts/check-onboarding-completeness.sh
# OK — all 59 deployed service(s) are placed in the LikeC4 model.  → exit 0
```

Placement resolves by an explicit `likec4: <id>` on the registry entry (for a subsumed/renamed element)
or a normalized key/name match against the model (kind-agnostic — component/gateway/store/node):

```
bash scripts/check-onboarding-completeness.sh --list | grep -E 'weyland-agent|dbt|port-k8s|promptfoo'
#   weyland-agent   -> weylandAgent      (matched)
#   dbt             -> dagster           (declared likec4: — dbt is subsumed by the Dagster element)
#   port-k8s-exporter -> portK8sExporter (matched)
#   promptfoo       -> promptfoo         (matched)
```

**What it caught on first run (fix-don't-file):** `weyland-agent`, `port-k8s-exporter`, `promptfoo` were
`deployed: true` but absent from the model. All three were added to `weyland.likec4` (validated ✓ Valid),
so the invariant now holds 59/59 — the guard did its job the moment it existed.

**2. Negative case — an unplaced deployed service MUST fail (proved with a fixture):**

```
# a deployed service with no matching element and no likec4: override
bash scripts/check-onboarding-completeness.sh   # (REGISTRY_FILE=fixture with a `ghost` service)
# UNPLACED — 1 deployed service(s) are not in the LikeC4 model:
#   - ghost (Ghost Service) — no LikeC4 element matches its key or name
# Fix: add the element to docs/architecture/weyland.likec4, or set `likec4: <id>` on the registry entry.  → exit 1
```

A declared `likec4:` pointing at a non-existent id is drift too (exit 1, "declared likec4:<id> is not in
the model"). `deployed: false` services (SaaS/IDE, the code-review group) are skipped, never flagged.

The guard runs **three** file checks, all fail-closed (negative cases RUN as bats fixtures):

- **SCHEMA** — an entry with no boolean `deployed` field → exit 1 ("SCHEMA … do not declare a boolean
  `deployed`"). This closes the guard's own footgun: a missing field would otherwise make the service
  read as *not deployed* and silently skip the placement check.
- **PORT** — a `deployed: true` service with no `port_component` → exit 1 ("PORT … declare no
  `port_component`").
- **PLACEMENT** — the LikeC4 resolution above.

The other DoD §6 surfaces are owned elsewhere and deliberately not re-checked: ServiceMonitor / dashboard
/ alert by the live coverage guards, Kuma by the UI (not git-checkable), and arch.md §6 is a curated
subset (only 14 of 31 ingress services live in it — the rest are documented in their own sections), so
there is no clean predicate to guard.

**3. Fail-closed — a read that could not run never reads as clean:**

```
REGISTRY_FILE=/nonexistent ... # → exit 2 "CANNOT RUN — registry unreadable"
# a model with no parseable elements                      → exit 2 (never "all unplaced")
# a registry with no `applications:`                       → exit 2
```

**Tests + wiring:** `scripts/tests/onboarding-completeness.bats` **10 passed** (incl. the live-invariant
case); `shellcheck --severity=warning` **0**. Runs in the `.woodpecker.yml` `repo-guards` step — pure
file analysis, secret-free, no cluster.

## The scaffolder (Phase 1b) — RUN 2026-09-07

`onboard-service.sh` writes both surfaces the guard checks, from one command, so a new service starts
onboarded-complete instead of being audited into compliance.

**Dry-run first (writes nothing):**

```
bash scripts/onboard-service.sh --key demo-svc --name "Demo Svc" --group ai-serving --zone ai \
  --capabilities "agent,retrieval-rag" --description "A demo service." --dry-run
# DRY RUN — would add to the registry (before the CODE-REVIEW / excluded section):
#   - {key: demo-svc, deployed: true, name: Demo Svc, group: ai-serving, ..., likec4: demoSvc, ...}
# DRY RUN — would add to LikeC4 (first element in zone 'ai'):
#         demoSvc = component "Demo Svc" "A demo service."
```

A real run appends the entry, inserts the element (id = camelCase(key), written as an explicit `likec4:`
so placement is unambiguous), then runs the Phase-1a guard to confirm — printing `onboarded '<key>'` and
the honest note that the element is **UNWIRED** (edges are a human follow-up, never guessed).

**Refusals RUN (fail-fast, no mutation):** a duplicate key → exit 1 ("already in the registry"); an
unknown `--zone`/`--group`/`--kind` → exit 1; a non-kebab key → exit 1; a missing required arg → exit 1.
`bats scripts/tests/onboard-service.bats` **8 passed** (incl. dry-run-writes-nothing + the end-to-end
"scaffolded service satisfies the guard"); shellcheck 0.

## UI walkthrough

N/A — repo tooling, no UI. Placement is visible in the rendered LikeC4 model (`likec4.weyland.lab`); a
guard failure surfaces as a red `repo-guards` step in Woodpecker like the other coverage guards.

## Teardown

Read-only. The guard reads `applications.yaml` + `weyland.likec4` and writes nothing.
