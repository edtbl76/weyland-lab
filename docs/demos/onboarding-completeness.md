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

**3. Fail-closed — a read that could not run never reads as clean:**

```
REGISTRY_FILE=/nonexistent ... # → exit 2 "CANNOT RUN — registry unreadable"
# a model with no parseable elements                      → exit 2 (never "all unplaced")
# a registry with no `applications:`                       → exit 2
```

**Tests + wiring:** `scripts/tests/onboarding-completeness.bats` **10 passed** (incl. the live-invariant
case); `shellcheck --severity=warning` **0**. Runs in the `.woodpecker.yml` `repo-guards` step — pure
file analysis, secret-free, no cluster.

## UI walkthrough

N/A — repo tooling, no UI. Placement is visible in the rendered LikeC4 model (`likec4.weyland.lab`); a
guard failure surfaces as a red `repo-guards` step in Woodpecker like the other coverage guards.

## Teardown

Read-only. The guard reads `applications.yaml` + `weyland.likec4` and writes nothing.
