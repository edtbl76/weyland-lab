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

## UI walkthrough

N/A — repo tooling + CronJobs, no UI surface. Outcomes surface on the existing pattern: per-repo SonarQube
dashboards (`dashboard?id=<repo>`) and the code-scan-suite → Port `security_scan` / `code_quality`.

## Teardown

The adhoc jobs are verification-only — delete them:
`kubectl -n weyland delete job sonar-scan-repos-adhoc sonar-scan-gradle-adhoc`. The weekly CronJobs
(`sonar-scan-repos` Sun 14:00 UTC, `sonar-scan-gradle` 15:00) are the durable path; the guard is read-only.
