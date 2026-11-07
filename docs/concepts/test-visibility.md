# Test visibility: inventory, history and flakiness (B189, EMA-248)

**Verdict (2026-11-06): Trunk Flaky Tests, free plan, fed from every CI pipeline. Allure 3 is the fallback if Trunk goes
away.** Runbook: `docs/runbooks/trunk-flaky-tests.md`.

## The question

Quality signals were scattered: pass and fail in Woodpecker logs, coverage in SonarQube, pipeline outcomes on Port's
`ci_pipeline`. Nothing showed which tests exist, how each one has behaved over time, or which ones flake. The deciding
requirement was a **Linear link**: a flaky test should become an issue without anyone noticing it first. Constraints: $0,
nothing heavy on mother (its memory is the lab's bottleneck).

## Candidates and verdicts

| Tool | Kind | Verdict | Why |
|---|---|---|---|
| **Trunk Flaky Tests** | SaaS, free plan | **ADOPT** | all 1,208 bats tests ingested on the first upload; per-test history, flaky and broken detection, quarantine, AI failure summary; Linear tickets **on Free**, filed and closed automatically; 0 RAM on the lab |
| **Allure 3** (3.21.0) | static report, CLI | **FALLBACK** | reads JUnit natively, per-test history from one history file, 0 RAM, no account. But no Linear, and its `flaky` flag means a retry *within* one run, so a test that flips between runs never trips it |
| QA Sphere | SaaS test management | **DON'T** (trialled 2026-11-06, owner) | `qas-cli` 0.10.1 uploaded the 1,208 bats results (runs 12–14, project WEY): per-test history works (90-day Insights) and a second upload matched cases by name. But **no flaky detection anywhere**; Linear issues are **manual**, one per result, in the integration's single project with **no label** (docs), so they break the Auto-Filed source-label rule; name-only identity **merged 19 different tests** (1,208 results → 1,189 cases) and would orphan history on a rename. Its strength, manual test cases and plans, is work the lab doesn't do. Revisit only if manual test plans appear |
| Testiny | SaaS test management | DON'T | Free excludes Automation and History (pricing page) |
| Kiwi TCMS | self-hosted | DON'T | no Linear |
| ReportPortal | self-hosted | DON'T | no Linear, and at least 6 GB of RAM on mother |
| TestDino, Qase, Tesults, Buildkite Test Engine | SaaS | DON'T | Playwright-only, Linear on a paid plan, or capped below the lab's volume |

## What Trunk costs us (the risks we accepted)

- **An unscoped token in CI.** The uploader takes only the legacy org token (v2 keys are rejected, and the v2 API has
  no upload endpoint). It lives in one Woodpecker secret that only the `trunk-upload` step requests (an image filter is not an option:
  Woodpecker applies those to plugins only).
- **The uploader fails open.** It can exit 0 on a failed upload and hang on a network problem, so `trunk-upload.sh`
  judges each upload from the printed output, with a timeout, and the step goes red (fail closed).
- **SaaS.** History lives in Trunk. Losing it loses trend data, not tests: the tests and their results stay in git and
  CI, and Allure can rebuild a static view from the same JUnit (`docs/dr.md`).
- **Span budget.** About 1M test results a month across every repo on Free (one non-bot committer). The limit is soft (a
  banner, not a block), so the runbook has a monthly check.
- **A UI bug.** The Create ticket modal shows the saved Linear defaults empty on its first open, so a hand-filed ticket
  can land with no project (EMA-334). Automatic tickets have not fired yet, so whether they are affected is unknown until
  the first one does; `check-linear-sync.sh` fails on any open issue with no project, which catches it either way.

## Where the issues go

Trunk's tickets can't carry a B/U number (no title template), so machine-filed issues got their own Linear project,
**Weyland Auto-Filed** (initiative `Automation`), with the source label `trunk-flaky`. U14's alert incidents moved there
too. The rule is in `AGENTS.md`; the design is in `docs/concepts/linear-evaluation.md` § Weyland Auto-Filed.

## Rollout

| Phase | Scope | State |
|---|---|---|
| 1 | Runners with built-in JUnit: pytest, bats, Maven, Gradle, sbt, phpunit, swift; one test case per golden path; the upload step | built 2026-11-06 |
| 2a | Remaining runners with built-in JUnit: lua (busted), C++ (doctest), erlang (eunit surefire), node's vitest and `node --test`; the four node lanes share one `node` variant so a project is not counted four times | built 2026-11-06 |
| 2b | Lanes that need a reporter package, each proposed with version and destination before it is added. **Done:** jest (`jest-junit` 17.0.0, installed per run outside the projects; all 9 node projects now report); go (`gotestsum` v1.13.0, sha256-pinned release binary; fixture + 3 golden paths); rust (`cargo-nextest` 0.9.149, sha256-pinned, generated config; no doctests run, none exist); dotnet (JunitXml.TestLogger 8.0.0, sha256-pinned nupkg, loaded by adapter path); R (`xml2` 1.6.0 from a dated Posit snapshot, for testthat's JunitReporter). **Next:** mix, lein, minitest, perl, dart, flutter | in progress |
| 3 | Lanes with no standard reporter (julia, haskell, ada, carton, the C runner): a lane-level report from the exit status and output | after 2 |
| 4 | The other repos: stud.io (same Woodpecker), then the eight others once their CI is known; one Trunk collection per repo, every ticket to Weyland Auto-Filed with a repo label | after a week of real span counts |

Found while wiring it: `shell-tests` and `test-shell` both run `scripts/tests`, so only `test-shell` reports; and the
golden-path loop used to `exit 2` at the first failed build, which hid every path after it (now it records the failure and
moves on).
