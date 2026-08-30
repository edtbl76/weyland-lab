# Flow — CI/CD hardening (B88 Track B, gaps #1–#5)

Sequence diagrams for the mechanisms added in the hardening bucket. Demo (RUN): [cicd-hardening.md](../demos/cicd-hardening.md).

## #1 Coverage ratchet — fail only on a drop vs the committed baseline

```mermaid
sequenceDiagram
    participant Lane as test lane (CI)
    participant R as coverage-ratchet.sh
    participant B as baseline.tsv (git)
    Lane->>R: run <lang> (coverage %)
    R->>B: read prior % for this project
    alt new project
        R->>B: record baseline (exit 0)
    else drop > tolerance
        R-->>Lane: REGRESSED (exit 1) — baseline NOT rewritten down
    else held or improved
        R->>B: ratchet up if improved (exit 0)
    end
```

## #2 Integration tier — black-box the live service (Ready ≠ correct response)

```mermaid
sequenceDiagram
    participant Step as test-integration-* (CI pod, in-cluster)
    participant Svc as live service (guard / redpanda)
    Step->>Svc: real request (POST /guard/*, rpk group list)
    Svc-->>Step: real response (verdict / consumer-group state)
    alt asserts hold
        Step-->>Step: exit 0 (assertions passed)
    else reachable but wrong
        Step-->>Step: exit 1 (real defect)
    else unreachable
        Step-->>Step: exit 2 (broken lane, fail closed)
    end
```

## #3 Per-build vuln scan + Δ vs deployed (drift-controlled)

```mermaid
sequenceDiagram
    participant B as build-images.sh
    participant SC as supply-chain.sh vuln
    participant T as trivy (pre-warmed DB)
    participant Reg as registry.weyland.lab
    B->>SC: vuln <new-ref> <deployed-ref>
    SC->>T: scan NEW image (--skip-db-update)
    T->>Reg: pull new
    T-->>SC: CVE set (new)
    SC->>T: scan DEPLOYED image (same DB)
    T->>Reg: pull deployed
    T-->>SC: CVE set (old)
    SC-->>B: count + Δ = new − old (loud ⚠ if new crit/high) — non-fatal
```

## #4 Post-deploy transaction — Ready ≠ works

```mermaid
sequenceDiagram
    participant Ship as ship-images.sh (txn_ok)
    participant Pod as in-cluster pod (kubectl exec)
    participant Svc as deployed service
    Ship->>Pod: per bumped image, run its transaction
    Pod->>Svc: real op (Dagster loadStatus / feast feature / tool-server /context/search)
    Svc-->>Pod: real result
    alt TXN_OK
        Pod-->>Ship: verified
    else TXN_FAIL <reason>
        Pod-->>Ship: named failure (Ready was a lie)
    end
```

## #5 Unleash deploy kill-switch — gate the MERGE, not the sync (selfHeal-proof)

```mermaid
sequenceDiagram
    participant Ship as ship-images.sh
    participant U as Unleash (weyland-ship-enabled)
    participant GH as GitHub (tag-bump PR)
    participant Argo as Argo CD (selfHeal)
    Ship->>U: ship_flag_allows? (in-cluster, client API)
    alt flag OFF
        U-->>Ship: disabled - HELD exit 3 - PR left open - git unchanged
        Note over Argo: nothing new in git HEAD so nothing to sync
    else flag ON or unreachable
        U-->>Ship: allow (fail-open)
        Ship->>GH: merge PR (new tag → git HEAD)
        Argo->>Argo: selfHeal syncs the new tag
    end
```
