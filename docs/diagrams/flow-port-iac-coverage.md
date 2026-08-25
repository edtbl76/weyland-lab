# Flow — Port IaC coverage (B137): the question `tofu plan` cannot ask

How Port's schema is kept under OpenTofu, and why a separate guard is needed to prove it. Sequence (Mermaid);
architecture placement in `arch.md` §6 (OpenTofu row) + [runbooks/port.md](../runbooks/port.md) § What is
deliberately UI-managed. Demo: [demos/port-iac-coverage.md](../demos/port-iac-coverage.md).

**The problem in one line:** `tofu plan` compares the code to the resources **tofu knows about**, so a blueprint
someone created in Port's UI is invisible to it — "no changes" and "half the catalog is unversioned" are the same
output. That is how the org reached 51 live blueprints against 13 codified over two months with a clean plan
throughout.

```mermaid
sequenceDiagram
    autonumber
    participant DEV as Human / Port UI
    participant PORT as api.port.io
    participant TF as tofu/port/*.tf<br/>(the CODE)
    participant STATE as tofu state<br/>(MinIO)
    participant PLAN as tofu plan
    participant CHK as check-port-iac-coverage.sh
    participant CI as Woodpecker<br/>port-iac-coverage

    rect rgb(255,235,235)
    Note over DEV,PLAN: How the gap opens — silently, one click at a time
    DEV->>PORT: create a blueprint in the UI
    PLAN->>STATE: read known resources
    PLAN->>PORT: refresh those resources only
    PLAN-->>DEV: "No changes."
    Note over PLAN: The new blueprint is not in state,<br/>so plan never asks about it. A clean plan<br/>and an unversioned catalog look identical.
    end

    rect rgb(235,245,255)
    Note over CHK,PORT: The guard asks the INVERSE question
    CI->>CHK: bash scripts/check-port-iac-coverage.sh
    CHK->>PORT: GET /v1/blueprints · /v1/scorecards · /v1/integration
    CHK->>TF: parse resource blocks by brace depth<br/>(the CODE, never the state)
    Note over CHK: state answers "what does tofu know about" —<br/>a resource can sit in state with no code behind it.<br/>That is exactly what B60's unexecuted state rm left.
    end

    rect rgb(240,255,240)
    Note over CHK: Classify every LIVE blueprint — codify what cannot recreate itself
    CHK->>CHK: _-prefixed → Port SYSTEM (11) — Port ships them
    CHK->>PORT: derive INTEGRATION-OWNED (15) from the live mappings
    Note over CHK: DERIVED, not an allow-list. Retire the integration<br/>and its blueprints stop being excused — no dead<br/>exception outliving its reason.
    CHK->>CHK: DORMANT_UI_MANAGED (4) — named, each with a reason
    CHK->>CHK: everything else MUST be in the code (21)
    end

    alt live schema the code does not describe
        CHK-->>CI: ❌ name it — codify, or excuse it WITH a reason
        CI-->>DEV: pipeline fails
    else full coverage
        CHK-->>CI: ✅ 51 = 21 codified + 30 excused
        CHK-->>DEV: print the REBUILD ORDER (6 relations)
        Note over DEV: codified relations target integration-owned<br/>blueprints, so a restore installs the<br/>integrations BEFORE tofu apply
    end

    rect rgb(255,250,230)
    Note over CHK: Fails CLOSED — an absent result is never a passing one
    Note over CHK: unreachable API · empty live list · unparseable .tf<br/>· a resource block with no literal identifier<br/>· a codified blueprint that is NOT live<br/>→ loud error, never a skip
    end
```

**The invariant:** every blueprint, scorecard and integration live in Port is either **in the code** or **excused by
one of three stated reasons**, and the excuse for the largest group is *derived from the live system* rather than
written down — so it expires on its own when the integration that justified it goes away.

**Why the excuses exist at all.** An Ocean integration creates its blueprints on install and **revises them on
upgrade** — github-ocean moved 6.8.1 → 6.9.4 in two days here. If tofu owned `githubRepository`, every upgrade
would read as drift and an apply would revert the integration's own schema, reintroducing the permanently-dirty
plan this whole item exists to cure.

Covered by 18 bats tests in `scripts/tests/port-iac-coverage.bats`, each verified by mutation — including one that
was vacuous on the first pass (the nested-identifier fixture put the decoy *after* the real value, so deleting the
parser's depth check kept it green).
