# Flow — the sealed placeholder (B147): how a credential can be perfectly restorable and authenticate to nothing

The failure that hid for 63 days, why every control reported green, and the guard that closes it.
Sequence (Mermaid); operations in [runbooks/secrets.md](../runbooks/secrets.md) § The placeholder guard.
Demo: [demos/secret-placeholders.md](../demos/secret-placeholders.md).

**The shape in one line:** DoD Pillar 6 asks whether secrets are **restorable**. `port-creds` was — a full
restore faithfully reproduced `YOUR_ID` / `YOUR_SECRET`, which authenticates to nothing.

```mermaid
sequenceDiagram
    autonumber
    participant DEV as Human
    participant K8S as Secret<br/>weyland/port-creds
    participant SEAL as kubeseal
    participant GIT as git
    participant ARGO as Argo + controller
    participant DAG as dagster-user-code
    participant PORT as Port

    rect rgb(255,235,235)
    Note over DEV,PORT: 2026-06-23 — how it started, and why nothing complained
    DEV->>K8S: create secret with YOUR_ID / YOUR_SECRET
    DEV->>SEAL: seal it
    SEAL->>GIT: weyland__port-creds.yaml
    ARGO->>K8S: adopt + reconcile (ownerRef: SealedSecret)
    DAG->>K8S: secretKeyRef -> env at pod start
    DAG->>PORT: POST /auth/access_token
    PORT-->>DAG: 401
    Note over DAG,PORT: the asset raises, the run fails, nobody is watching a<br/>Dagster asset that was never known to have worked.<br/>ai_session stays at 37 entities — all hand-seeded<br/>23 MINUTES BEFORE the credential even existed.
    end

    rect rgb(245,245,245)
    Note over K8S,GIT: every control said GREEN for 63 days
    Note over K8S: sealed ✅  ·  committed ✅  ·  Argo-applied ✅<br/>DATA 2 ✅  ·  mounted by a running pod ✅<br/>ownerReferences: [SealedSecret] ✅
    Note over GIT: Pillar 6 "secrets restorable" — HONESTLY SATISFIED.<br/>The restore works perfectly. It restores a 401.
    end

    rect rgb(255,245,225)
    Note over DEV,ARGO: 2026-08-25 — the trap when you try to fix it in the cluster
    DEV->>K8S: kubectl apply real credentials
    DEV->>K8S: verify -> HTTP 200 ✅
    DEV->>DAG: rollout restart
    ARGO->>K8S: selfHeal re-applies the sealed CR FROM GIT
    K8S-->>DEV: back to YOUR_ID
    Note over DEV,ARGO: the revert lands on Argo's sync interval, so verifying<br/>immediately after the change PASSES. You cannot fix a<br/>sealed secret in the cluster — only in git.
    end

    rect rgb(235,255,235)
    Note over DEV,PORT: the sequence that works — order matters
    DEV->>K8S: 1. update the live Secret (so kubeseal can read it)
    DEV->>SEAL: 2-3. annotate + seal ONE secret
    SEAL->>GIT: 4. COMMIT + PUSH
    GIT->>ARGO: sync to the new revision
    ARGO->>K8S: controller writes a WORKING credential
    DEV->>DAG: 5. rollout restart — AFTER the sync,<br/>because secretKeyRef injects at pod START
    DAG->>PORT: 62 upserts, 0 errors
    PORT-->>DEV: 37 -> 62 entities, 25 createdBy the INTEGRATION
    end

    rect rgb(235,245,255)
    Note over DEV,GIT: the guard, so it cannot happen again unseen
    DEV->>GIT: read the allow-list OUT of seal-secrets.sh<br/>(never a second copy — two lists drift silently)
    DEV->>K8S: decode every value of every allow-listed secret
    alt empty, or placeholder vocabulary in a short single-line value
        DEV-->>DEV: ❌ name the secret AND the key
    else short single-line token that looks real
        DEV-->>DEV: ok
    else multi-line or >200 chars
        Note over DEV: CONFIG, not a credential — never inspected.<br/>clickhouse-users is an XML doc starting <clickhouse><br/>and the first version flagged it. A guard that cries<br/>wolf gets muted, and a muted guard is worth nothing.
    end
    end
```

**The invariant:** every credential in the sealed allow-list is decoded and looked at, and anything that is
empty or reads as a placeholder fails the run by name — unless it carries a written exception stating the
condition that makes it legitimate.

**Why "restorable" was never the right question.** Pillar 6's check is structural: is the secret in git,
does Argo apply it, does the pod mount it. All three can be true of a value that is worthless. The only
check that distinguishes a credential from a placeholder is decoding it — which is why the guard does the
one thing no other control in the estate does.

Covered by 20 bats tests in `scripts/tests/secret-placeholders.bats`, including the multi-line and XML
cases that broke the first implementation.
