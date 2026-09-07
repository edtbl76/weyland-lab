# Flow — declared-image provenance invariant (B88)

The Gatekeeper `require-signed-images` constraint only AUDITS running pods in dryrun, so its
"0 violations" is transient. Two guards turn it into a durable invariant — *every declared image is
from a reviewed source* — with ONE decision core fed two ways. Runbook:
[supply-chain.md § the provenance invariant](../runbooks/supply-chain.md#the-provenance-invariant--what-makes-0-violations-trustworthy);
demo: [image-provenance.md](../demos/image-provenance.md). LikeC4 placement is N/A for the CI guard
(it deploys nothing); the enumerator CronJob rides the existing `monitoring` Argo app.

## Two feeders, one decision core

```mermaid
flowchart TB
    subgraph FEED [feeders — produce IMAGE_LIST + the policy]
        direction LR
        CI["CI (repo-guards): scan k8s manifests<br/>image: strings — PR-time, pre-deploy"]
        CRON["cron (03:10): kubectl-enumerate ALL declared<br/>workloads live — running or not, chart-rendered"]
        POL["policy: image-signatures.yaml (CI)<br/>OR the live K8sImageSignature constraint (cron)"]
    end
    subgraph CORE [check-image-provenance.sh — the SAME core, byte-identical in both]
        direction TB
        Q{"for each image:<br/>reviewed?"}
        R1["allowedRegistries prefix<br/>(registry.weyland.lab/)"]
        R2["exemptImages prefix<br/>(reviewed publisher, by full path)"]
        R3["implicit single-segment<br/>Docker Hub official (library/*)"]
    end
    CI --> Q
    CRON --> Q
    POL --> Q
    Q --> R1 & R2 & R3
    R1 & R2 & R3 --> V{"any rule matched?"}
    V -->|yes| OK["reviewed — continue"]
    V -->|no| BAD["UNREVIEWED — collect + name"]
```

## Fail-closed exit contract

```mermaid
flowchart TD
    S[run] --> P{policy loaded?}
    P -->|no / unparseable| E2A["exit 2 — could not judge"]
    P -->|yes| I{images enumerated?}
    I -->|none / empty fed list| E2B["exit 2 — refuse a clean estate on a failed read"]
    I -->|yes| NS{"image's namespace<br/>in excludedNamespaces?"}
    NS -->|yes| SKIP[skip — cluster infra we don't build]
    NS -->|no| J{all reviewed?}
    J -->|yes| E0["exit 0 — invariant holds"]
    J -->|no| E1["exit 1 — name every unreviewed image + the fix"]
```

- **One core, two feeders:** the git scan (CI, pre-merge) and the kubectl enumerator (cron, live) both
  produce an `IMAGE_LIST`; the decision — allowlist OR exempt-prefix OR implicit-official — is identical
  to the constraint's Rego and read from the same policy, so the guard and the admission control can
  never disagree. The enumerator's byte-identical copy is asserted in `image-provenance.bats`.
- **Fail closed:** exit **1** = a defect (an unreviewed image, named); exit **2** = the guard could not
  run (no policy, no images). They are never conflated — a broken guard must not read as a clean estate,
  the rule the whole coverage-guard family enforces. The cron's kubectl init-dump failing fails the Job.
