# Demo — Repo coverage parity (B138)

The lab has 8 active repos + 1 stale (`midi_real_book`, catalog-only), and every repo-watching tool once tracked
a *different* subset. B138 established **one canonical source of truth** — [`repos.yaml`](../../repos.yaml) at the
repo root — and reconciled every lane to it, with a **drift guard** (`check-repo-coverage.sh`, in `repo-guards`)
that fails when any enforced lane diverges. Audit + design:
[ci-test-categories parity is B138; runbook](../runbooks/repo-coverage.md).

Mostly repo tooling, but the SonarQube multi-repo lanes are real k8s CronJobs. No UI — the **CLI walkthrough IS
the test**, run against live infra, including the **negative case**.

## CLI walkthrough (RUN 2026-09-18)

**1. The drift guard — every enforced lane at parity with the SoT:**

```
bash scripts/check-repo-coverage.sh
# repo-coverage: 9 canonical repos, enforcing lanes ['backup', 'catalog', 'iac', 'pr', 'scan']
#   [ENFORCED] iac/scan/pr/catalog/backup — ✓ parity   [pending] ci (per-repo .woodpecker.yml)
# ✓ all enforced lanes in parity with repos.yaml   → exit 0
```

**2. Multi-repo SonarQube — the 6 non-Java repos, incl. all 3 private ones (`freejack`/`startme-curator`/`MyBodyGraph`):**

```
kubectl -n weyland create job sonar-scan-repos-adhoc --from=cronjob/sonar-scan-repos
kubectl -n weyland logs job/sonar-scan-repos-adhoc | grep -E 'sonar-scan-repos:|EXECUTION'
# Algopedia … EXECUTION SUCCESS · MyBodyGraph … SUCCESS · emangini-tailwind-nextjs-contentlayer … SUCCESS
# freejack … SUCCESS · startme-curator … SUCCESS · stud.io … SUCCESS
# === sonar-scan-repos: all repos processed (rc=0) ===
```

The private repos cloning + scanning cleanly proves the `pr-lifecycle-github` `Contents:read` token reaches
them — the silent-skip failure B138 exists to kill.

**3. SonarQube for the Gradle repo (compile-then-scan):**

```
kubectl -n weyland create job sonar-scan-gradle-adhoc --from=cronjob/sonar-scan-gradle
kubectl -n weyland logs job/sonar-scan-gradle-adhoc | tail -3
# ANALYSIS SUCCESSFUL … dashboard?id=ServiceTransformation   → EXECUTION SUCCESS
```

The `gradle-build` init container runs `./gradlew classes`, and Sonar's Java/JaCoCo sensors bind to the compiled
output — the reason ServiceTransformation needs its own pipeline (source-level scanning can't analyze Java).

## Negative case — the guard caught a real bug on first run (RUN 2026-09-18)

The first live `sonar-scan-repos` failed on exactly one repo:

```
======================= sonar-scan-repos: stud.io =======================
ERROR File app/controlroom_backend/tests/test_config.py can't be indexed twice. Please check that
      inclusion/exclusion patterns produce disjoint sets for main and test files
EXECUTION FAILURE
=== sonar-scan-repos: all repos processed (rc=1) ===
```

**Root cause:** `stud.io` is the only repo with its **own** `sonar-project.properties` (a deliberate main/test
split), and the runner forced `-Dsonar.sources=.`, re-adding stud.io's test dirs to the main set. **Fix:** the
runner now defers to a repo's own `sonar-project.properties` when present, supplying source/exclusion defaults
only for repos without one. Re-run after the fix → **`stud.io … EXECUTION SUCCESS`, rc=0** (walkthrough §2). A
guard nobody has watched fail is not a guard; this one failed loud, we fixed it, and it's green.

## Source-only Java, and the Sunday move (RUN 2026-10-19, B229 + B228)

**The failure (negative case, observed live).** The 2026-10-18 `sonar-scan-repos` Job failed `BackoffLimitExceeded`:
7 repos `EXECUTION SUCCESS`, freejack `EXECUTION FAILURE` with
`AnalysisException: Your project contains .java files, please provide compiled classes with sonar.java.binaries`, and
`ScheduledJobFailed` / `KubeJobFailed` / `ScheduledJobStale` firing. freejack holds 1,704 `.java`: 177 are its own
lessons (no pom/Gradle, so no compiled classes) and 1,527 are vendored third-party code under `vendor/` (excluded).

**The decision, tested.** The runner now points `sonar.java.binaries` at an empty directory for any repo with `.java`
outside `node_modules`/`.git` whose own `sonar-project.properties` does not set it — source analyzed as-is:

[rogueone]
```
cd /home/edwardmangini/IdeaProjects/weyland && docker run --rm -v "$PWD:/repo:ro" -w /repo --entrypoint sh bats/bats:latest -c 'apk add --no-cache python3 py3-yaml >/dev/null 2>&1; bats scripts/tests/sonar-scan-repos.bats'
```
7/7 ok — including a case that fails on any `find` call: the scanner image (`sonarsource/sonar-scanner-cli`, Amazon
Linux 2023) has no `find`, so a find-based check would have silently skipped the setting while bats (which has find)
stayed green. The check uses `ls -R` + `awk`, run in both images with identical results.

**Live** (after the push; Argo applied it in ~60 s):

[mother]
```
kubectl -n weyland create job sonar-scan-repos-smoke --from=cronjob/sonar-scan-repos
```
Output (run): all 8 repos `EXECUTION SUCCESS`, `=== sonar-scan-repos: all repos processed (rc=0) ===`; freejack ran
`Sensor JavaSensor [java]` with only the expected `Dependencies/libraries were not provided` warning. SonarQube's own
count for the freejack project: **177** `.java` files (java ncloc 2,825) — every lesson file, none of `vendor/`.
`ScheduledJobStale` resolved; the two failed-Job alerts clear when that Job's 72 h TTL removes it.

**The Sunday move (B228)** — the four weekly scans left the working day (Design Rule #5) for the NY clock:

[mother]
```
kubectl -n weyland get cronjob sonar-scan sonar-scan-repos sonar-scan-gradle code-scan-suite -o custom-columns=NAME:.metadata.name,SCHEDULE:.spec.schedule,TZ:.spec.timeZone
```
Output (run): `sonar-scan 0 3 * * 0`, `sonar-scan-repos 15 3 * * 0`, `sonar-scan-gradle 30 3 * * 0`,
`code-scan-suite 0 4 * * 0`, all `America/New_York` (were 12–15:00 `Etc/UTC` = 08–11:00 NY). The proof that they run
there is the next Sunday's Job start times.

## UI walkthrough

N/A — repo tooling + CronJobs, no UI surface. Outcomes surface on the existing pattern: per-repo SonarQube
dashboards (`dashboard?id=<repo>`) and the code-scan-suite → Port `security_scan` / `code_quality`.

## Teardown

The adhoc jobs are verification-only — delete them:
`kubectl -n weyland delete job sonar-scan-repos-adhoc sonar-scan-gradle-adhoc`. The weekly CronJobs
(`sonar-scan-repos` Sun 03:15 NY, `sonar-scan-gradle` 03:30 — B228) are the durable path; the guard is read-only.
