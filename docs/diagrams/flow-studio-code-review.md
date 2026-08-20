# Flow: STUD.io code-review stack on a PR (B118)

How the adopted code-review stack reviews a **STUD.io** pull request. STUD.io (`edtbl76/stud.io`) is a **public**
repo, so the cloud review Apps are **GitHub-hosted and event-driven** — GitHub pushes the PR event *out* to each
App, which reviews on its own infra and posts a **check** back. That outbound-from-GitHub direction is exactly why
the lab's **LAN-webhook wall doesn't apply** (nothing has to reach `*.weyland.lab`). Separately, STUD.io's Woodpecker
CI run reports its outcome to Port's `ci_pipeline` reliability signal (B63) — a different path from the review checks.
Verified live on **PR #121** (2026-08-19): DeepSource (7 analyzers), CodeScene (project 78184), and Sourcery all
posted passing checks; CodeRabbit + Qodo reviewed in the conversation. Greptile is not yet installed on this repo.

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant GH as GitHub (edtbl76/stud.io, public)
    participant DS as DeepSource (App)
    participant CS as CodeScene (project 78184)
    participant SR as Sourcery / CodeRabbit / Qodo (Apps)
    participant WP as Woodpecker farm (backend=local)
    participant Port as Port ci_pipeline / weyland_ci_reliability
    Dev->>GH: open / update PR
    par cloud review Apps (event pushed OUT — no LAN reach needed)
        GH->>DS: PR webhook
        DS-->>GH: 7 analyzer checks (Python·JS·Go·SQL·Secrets·Shell·Docker)
    and
        GH->>CS: PR webhook
        CS-->>GH: Code Health Review delta check
    and
        GH->>SR: PR webhook
        SR-->>GH: review checks + PR-conversation comments
    end
    Note over GH: branch protection requires ci/woodpecker/pr/main (the CI check), not the review Apps
    Dev->>WP: woodpecker-cli pipeline create (LAN CLI — no GitHub push webhook to the LAN)
    WP->>Port: notify-port (terminal status → ci_pipeline, B63)
    Dev->>GH: read checks + reviews; squash-merge when green
    Note over GH,Port: Greptile = the one App not yet installed on edtbl76/stud.io (browser install pending)
```
