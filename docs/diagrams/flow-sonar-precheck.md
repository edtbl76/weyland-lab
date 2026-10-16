# Flow: SonarQube pre-check before handoff (2026-10-13)

`scripts/sonar_api.py precheck <file>...` runs the CI gate's rules on changed files before a handoff, in a throwaway
project. Two choices in it are not obvious, so they are drawn: the scanner returns before Sonar has processed the
report (so it waits), and a scratch project's gate passes with issues open (so the verdict is the findings).
Runbook: [code-quality.md](../runbooks/code-quality.md). Demo: [sonar-precheck.md](../demos/sonar-precheck.md).

```mermaid
sequenceDiagram
    participant A as Agent or owner (rogueone)
    participant P as sonar_api.py precheck
    participant D as sonar-scanner-cli (Docker, host network, invoking user)
    participant S as SonarQube (mother NodePort 30969)

    A->>P: precheck file1 file2 …
    Note over P: any argument not a file → exit 2 before touching Sonar
    P->>P: copy the files to a temp dir, keeping repo-relative paths
    P->>S: mint a token named weyland-lab-precheck-PID
    P->>D: scan the temp dir as project weyland-lab-precheck-PID
    D->>S: upload the analysis report
    D-->>P: exit code (non-zero → exit 2, ERROR lines shown)
    loop until the task queue is empty, at most 300 s
        P->>S: GET ce/component
    end
    Note over P: status not SUCCESS, or timeout → exit 2
    P->>S: GET measures/component files
    Note over P: 0 files analysed → exit 2 (analysed nothing is not clean)
    P->>S: GET issues/search + hotspots/search on the scratch project
    P->>S: GET hotspots reviewed SAFE on weyland-lab for the same files
    Note over P: a scratch hotspot matching file + rule + message of a reviewed one is listed, not counted
    P->>S: GET issues + TO_REVIEW hotspots already open on weyland-lab for the same files
    Note over P: matching file + rule + message → "already open", listed, not counted (old code)
    P->>P: git diff -U0 origin/main → the lines this change edits (2026-10-16)
    Note over P: an "already open" finding ON an edited line counts as NEW (CI's gate counts that line as new code) — git cannot answer → exit 2
    Note over P: verdict = findings, never the scratch gate (no new-code period, it passes with issues open)
    P->>S: delete the project, revoke the token (always, also on failure)
    Note over P: a token that could not be revoked → exit 2
    P-->>A: clean → exit 0, findings named → exit 1
```
