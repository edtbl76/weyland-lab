# Flow: CI test results → Trunk Flaky Tests → Linear (B189)

Every pipeline's test results reach Trunk, which keeps each test's history and files a Linear issue when a test turns
flaky or broken, then closes it when the test is healthy again. Runbook:
[trunk-flaky-tests.md](../runbooks/trunk-flaky-tests.md). Verdict: [test-visibility.md](../concepts/test-visibility.md).

```mermaid
sequenceDiagram
    participant L as Test lanes (test-python, test-shell, test-java, ...)
    participant G as golden-path-smoke
    participant W as Shared workspace reports/junit
    participant U as trunk-upload step
    participant T as Trunk Flaky Tests
    participant Li as Linear (Weyland Auto-Filed)
    L->>W: one JUnit report per project (normal runs only, never self-check)
    G->>W: one test case per golden path (OK, BUILD, APPLY or SMOKE FAILED)
    Note over U: runs after green AND red pipelines
    U->>U: download CLI 0.16.1, check its sha256
    loop each source directory (one variant)
        U->>T: upload JUnit (variant = source)
        T-->>U: printed Upload link and Test Report
    end
    alt any upload not confirmed in the output, or timed out
        U-->>U: step red (fail closed)
    end
    T->>T: monitors mark tests flaky or broken
    T->>Li: issue in Weyland Auto-Filed, label trunk-flaky, priority Low
    T->>Li: test healthy again, so close the issue
```

- **The CLI's exit code is not the verdict.** It exits 1 when tests failed (the upload still landed), 70 when refused,
  and has exited 0 after a failed upload. `trunk-upload.sh` reads the printed output instead.
- **Self-check runs never report.** Their deliberate failure would reach Trunk as a test that fails every build.
- **`shell-tests` does not report.** It runs the same `scripts/tests` as `test-shell`, which does.
