# Flow — API lifecycle governance (B155)

The estate's APIs are governed across their whole lifecycle from one catalog (`apis.yaml`): a PR-time
lifecycle guard + a runtime drift cron, both over the same catalog + committed contract snapshots, with
one breaking-change engine. Concept: [api-lifecycle.md](../concepts/api-lifecycle.md); demo:
[api-lifecycle.md](../demos/api-lifecycle.md). The `api-drift` CronJob is modelled in LikeC4 as
`apiDrift` (obs group); the CI guard + engine are repo tooling (LikeC4 N/A).

## Two enforcement points, one catalog + one engine

```mermaid
flowchart TB
    CAT["apis.yaml — the catalog<br/>owner · kind · status · version · consumers · spec · spec_source"]
    SNAP["docs/api/specs/ — committed contract snapshots<br/>(5 OpenAPI + realm A2A card)"]
    ENG["api_spec_diff.py — breaking-change engine<br/>removed op/field/enum · new required = BREAKING"]

    subgraph CI ["PR time — check-api-lifecycle.sh (repo-guards)"]
        L1["owner resolves · kind/status/version declared"]
        L2["published openapi/a2a ⇒ a snapshot exists"]
        L3["deprecated ⇒ retire_by + successor · retired ⇒ no consumers"]
    end
    subgraph RUN ["nightly 03:20 — api-drift CronJob"]
        D1["fetch each API's LIVE spec (spec_source)"]
        D2["diff LIVE vs committed snapshot"]
        D3["breaking drift ⇒ fail Job ⇒ Telegram; unreachable ⇒ skip"]
    end

    CAT --> L1 --> L2 --> L3
    CAT --> D1 --> D2 --> D3
    SNAP --> D2
    ENG --> D2
    ENG -.on-demand: compare a proposed spec to the snapshot.-> DEV["a human bumping a version"]
```

## Lifecycle stages the catalog governs

```mermaid
flowchart LR
    DESIGN["design"] --> PUB["published<br/>(snapshot + version governed)"]
    PUB -->|"breaking change<br/>⇒ MAJOR bump + re-capture"| PUB
    PUB --> DEP["deprecated<br/>(retire_by + successor)"]
    DEP -->|"consumers migrated off"| RET["retired<br/>(no consumers)"]
```

- **One catalog, two enforcement points:** the lifecycle guard governs the *declaration* at PR time; the
  drift cron governs the *deployed reality* nightly. Both read `apis.yaml`; both fail-closed.
- **The engine is the objective arbiter of "breaking":** the same classifier runs in the cron (live vs
  snapshot) and on-demand (a human comparing a proposed spec before bumping). It never guesses — an
  unknown/mismatched pair is *cannot-compare*, not a silent pass.
- **Honest scope:** only typed contracts (OpenAPI/A2A) get snapshots + drift detection; MCP/OpenAI-shape
  APIs are catalogued (owner/version/status) but not yet snapshotted, and the guard says so.
