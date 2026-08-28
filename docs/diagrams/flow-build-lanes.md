# Flow — per-language build lanes + supply chain (B88)

How one hardcoded test step became nine languages, three scan lanes and a signed supply chain, and
why the exit codes are the load-bearing part. Architecture placement: `arch.md` + the LikeC4 model.

## The defect it replaced

```mermaid
flowchart LR
    subgraph BEFORE["Before B88"]
      S1["shell-tests<br/>bats scripts/tests/"] -->|"a DIRECTORY —<br/>auto-discovers"| OK1["scales with the repo"]
      S2["unit-tests<br/>cd services/weyland-guard<br/>&& pytest"] -->|"ONE service,<br/>named by path"| BAD["a suite added anywhere else<br/><b>is never executed</b>"]
    end
    BAD --> GREEN["reports GREEN<br/><i>because nothing ran it</i>"]

    style BAD fill:#ffdddd,stroke:#cc0000
    style GREEN fill:#ffdddd,stroke:#cc0000
    style OK1 fill:#ddffdd,stroke:#00aa00
```

The shell lane scaled; the Python lane did not. B78's Open Food Facts work was about to add
`weyland-dagster`'s first pytest suite — and nothing would have run it. **Green by absence**, in the
test harness itself, where it is hardest to notice.

## Discovery keys on TESTS, not on manifests

```mermaid
flowchart TD
    F["find test files<br/>test_*.py · *.bats · *_test.go<br/>*Test.java · *.test.ts · #[test]"] --> R{"resolve to the<br/>owning project root"}
    R -->|"go / rust / java / node"| M["walk UP to go.mod ·<br/>Cargo.toml · pom.xml ·<br/>package.json"]
    R -->|"python"| PY["parent of tests/<br/>(pytest runs FROM the project)"]
    R -->|"shell"| SH["the dir CONTAINING<br/>the .bats files<br/>(bats runs IN it)"]
    M --> U["unique set of roots"]
    PY --> U
    SH --> U

    style PY fill:#fff4dd,stroke:#cc8800
    style SH fill:#fff4dd,stroke:#cc8800
```

**Python and shell need OPPOSITE roots**, and conflating them was a real bug: applying python's
rule to shell resolved `scripts/tests` → `scripts`, where `bats .` finds nothing and exits 1 — a
healthy 289-test suite reported as an estate defect.

Keying on *manifests* instead was worse in both directions: it missed `weyland-guard` (the only
Python suite CI runs, which has `tests/` and no manifest) and matched five services that have a
manifest and no tests, where `pytest` exits **5** → five false failures.

## The exit codes are the design

```mermaid
flowchart TD
    A["run-lang-tests.sh LANG"] --> FX{"fixture passes?"}
    FX -->|no| E2["<b>exit 2</b><br/>the LANE is broken"]
    FX -->|"toolchain absent"| E2
    FX -->|"fixture missing"| E2
    FX -->|yes| P{"every discovered<br/>project passes?"}
    P -->|"no — real failure"| E1["<b>exit 1</b><br/>the ESTATE has a defect"]
    P -->|"pytest exit 2/3/4"| E2C["<b>exit 2</b><br/>could not COLLECT —<br/>nothing was tested"]
    P -->|"pytest exit 5"| E2N["<b>exit 2</b><br/>discovered it, collected<br/>NO tests — name the path"]
    P -->|yes| E0["<b>exit 0</b><br/>fixture + N project(s) passed"]

    style E2 fill:#ffdddd,stroke:#cc0000
    style E2C fill:#ffdddd,stroke:#cc0000
    style E2N fill:#ffdddd,stroke:#cc0000
    style E1 fill:#fff4dd,stroke:#cc8800
    style E0 fill:#ddffdd,stroke:#00aa00
```

**Conflating 1 and 2 makes a broken runner read exactly like broken code.** A missing dependency is
not a failing test — `weyland-guard` could not be *collected* (no `prometheus_client`) and the first
version of this called that "the estate has a failing test". Nothing had been tested at all.

**Why every lane ships a hello-world fixture:** a language with no production code yet (Go, Rust)
has nothing to run, and "nothing to run" is one careless line from "green". The fixture deletes that
state — every lane always executes a real test, so the image, toolchain, discovery and runner are
continuously proven. `--self-check` then runs each fixture's *deliberately failing* test and asserts
the runner propagates it: **a lane never seen failing is not a lane.**

## The pipeline

```mermaid
sequenceDiagram
    autonumber
    participant WP as Woodpecker
    participant T as 6 test lanes<br/>(9 languages)
    participant S as 3 scan lanes<br/>(13 tools)
    participant RG as rego-policies
    participant BK as buildkitd
    participant SC as supply-chain.sh
    participant REG as registry.weyland.lab

    WP->>T: pinned image per lane, --self-check FIRST
    Note over T: python · shell · java · go · rust ·<br/>ts · js · react · nextjs
    WP->>S: rust · java · node scanners
    Note over S: clippy/cargo-audit/cargo-deny · spotbugs/pmd/<br/>checkstyle/error-prone · eslint/tsc/npm-audit/licences<br/>findings are COUNTS, not gates
    WP->>RG: compile every ConstraintTemplate + exercise the policy
    Note over RG: kubeconform SKIPS Gatekeeper CRDs —<br/>before this, NO Rego here was ever validated

    WP->>BK: build + push the git-sha tag
    BK->>REG: push
    BK->>SC: supply-chain.sh all IMAGE
    SC->>SC: syft -> CycloneDX + SPDX
    SC->>REG: cosign sign
    SC->>REG: cosign attest (SLSA provenance)
    SC->>SC: trivy --scanners license
    Note over SC: NEVER fails the build — an unsigned image is a<br/>gap to fix, not a broken build. Never silent either.
```

## Admission — what it can and cannot do

```mermaid
flowchart LR
    POD["Pod admission"] --> GK["Gatekeeper<br/>K8sImageSignature"]
    GK --> Q{"image from<br/>registry.weyland.lab/<br/>or explicitly exempt?"}
    Q -->|yes| ADMIT["admitted"]
    Q -->|no| VIOL["violation recorded<br/><b>dryrun — nothing blocked</b>"]
    GK -.->|"CANNOT call cosign:<br/>no network egress<br/>from the admission path"| X["registry"]
    CI["CI: cosign verify"] -->|"the REAL cryptographic check,<br/>before deploy"| X

    style VIOL fill:#fff4dd,stroke:#cc8800
    style X fill:#eeeeee,stroke:#999999
    style CI fill:#ddffdd,stroke:#00aa00
```

**Stated rather than hidden:** Gatekeeper's Rego runs with no network egress, so it cannot verify a
signature. It asserts the checkable thing — provenance by registry — while `cosign verify` does the
real work in CI. Full in-cluster verification needs a controller that can reach the registry
(Kyverno + cosign, or sigstore-policy-controller); that is a separate decision.

The constraint ships in **`dryrun`** because every image running today is unsigned and `deny` would
reject all of them. See [runbooks/supply-chain.md](../runbooks/supply-chain.md) for the
promote-to-deny checklist.
