# Demo — SonarQube pre-check before handoff (2026-10-13)

CI's `sonar-gate` step blocks the build and that night's image ship, and nothing in the local guard suite runs Sonar.
`scripts/sonar_api.py precheck <file>...` scans changed files in a throwaway project with the same rules `weyland-lab`
uses, names every finding, and always removes the project and its token. DoD pillar 7 and `AGENTS.md` require
`precheck: clean` before handoff. Runbook: [code-quality.md](../runbooks/code-quality.md). All RUN 2026-10-13 on
rogueone. There is no UI: the CLI walkthrough is the whole demo.

## Sequence diagram
See [../diagrams/flow-sonar-precheck.md](../diagrams/flow-sonar-precheck.md).

## Prerequisites
`scripts/.env` with `SONAR_ADMIN_PW` (it mints and revokes a token per run). Docker (the scanner runs in
`sonarsource/sonar-scanner-cli:latest`, as the invoking user).

## CLI walkthrough

**1. Clean files pass** (exit 0):
[rogueone]
```
set -a && . /home/edwardmangini/IdeaProjects/weyland/scripts/.env && set +a && cd /home/edwardmangini/IdeaProjects/weyland && python3 scripts/sonar_api.py precheck nodes/mother/lab/weyland-platform/scripts/issue_time_report.py scripts/sonar_api.py
```
```
  already reviewed SAFE on weyland-lab: scripts/sonar_api.py:33 — Using http protocol is insecure. Use https instead
precheck: clean (2 files scanned, 0 issues, 0 hotspots, 1 already reviewed)
```
The `http` hotspot was reviewed SAFE on the real project long ago; a scratch project knows no review history, so it is
listed but not counted (matched on file, rule and message, because lines move).

**2. The whole working tree** (the runbook form):
[rogueone]
```
set -a && . /home/edwardmangini/IdeaProjects/weyland/scripts/.env && set +a && cd /home/edwardmangini/IdeaProjects/weyland && python3 scripts/sonar_api.py precheck $(git diff --name-only --diff-filter=d HEAD; git ls-files --others --exclude-standard)
```
Prints `precheck: clean (N files scanned, …)`. Files Sonar does not analyse (Markdown, YAML) are not counted.

## Negative cases — the check must be seen failing

**3. A planted finding** (exit 1, each finding named):
[rogueone]
```
printf 'import os\n\ndef f(p):\n    password = "hunter2"\n    return password\n' > /home/edwardmangini/.claude/jobs/de8fed56/tmp/pc/planted.py && set -a && . /home/edwardmangini/IdeaProjects/weyland/scripts/.env && set +a && python3 /home/edwardmangini/IdeaProjects/weyland/scripts/sonar_api.py precheck /home/edwardmangini/.claude/jobs/de8fed56/tmp/pc/planted.py; echo "exit=$?"
```
```
  MAJOR python:S1172 planted.py:3 — Remove the unused function parameter "p".
  MAJOR python:S2068 planted.py:4 — "password" detected here, review this potentially hard-coded credential.
precheck: FINDINGS (1 files scanned, 2 issues, 0 hotspots)
exit=1
```
The scratch project's own quality gate PASSED on this file: a first analysis has no new-code period. That is why the
verdict is the findings, never the scratch gate.

**4. Could not scan** (exit 2, never read as clean):
```
python3 /home/edwardmangini/IdeaProjects/weyland/scripts/sonar_api.py precheck no/such.py; echo "exit=$?"
sonar_api: precheck: not a file: no/such.py
exit=2
```
Also exit 2, each covered by a test: the scanner fails (on the default Docker network it could not resolve
`mother.weyland.lab`), the analysis fails or times out, Sonar analysed 0 files (the first live run read the project
before Sonar had processed the upload), or the cleanup could not revoke the token.

**5. An already-open finding on an edited line** (added 2026-10-16, RUN 2026-10-16; exit 1). CI #387 and #388 failed
on an S1192 the precheck had listed as "already open": the edit touched a line carrying one copy of a duplicated
literal, and CI's gate counts an edited line as new code. Run in a scratch clone so the repo is untouched. Edit the
`scan.py` line that carries an already-open S1192 (`"application/json"` ×4):
[rogueone]
```
T=$(mktemp -d) && git clone --quiet /home/edwardmangini/IdeaProjects/weyland $T/w && cd $T/w && F=nodes/mother/lab/weyland-platform/services/scan-suite/scan.py && L=$(grep -n 'headers={"Content-Type": "application/json"})' $F | head -1 | cut -d: -f1) && sed -i "${L}s/\$/  # demo edit/" $F && set -a && . /home/edwardmangini/IdeaProjects/weyland/scripts/.env && set +a && python3 scripts/sonar_api.py precheck $F; echo "exit=$?"
```
```
  CRITICAL python:S1192 nodes/mother/lab/weyland-platform/services/scan-suite/scan.py:82 — Define a constant instead of duplicating this literal "application/json" 4 times. (already open, but on a line this change edits — CI counts it as new code)
precheck: FINDINGS (1 files scanned, 1 issues, 0 hotspots, 13 already open)
exit=1
```
Revert the edit (`git checkout -- $F`) and the same command prints `precheck: clean (1 files scanned, 0 issues, 0
hotspots, 14 already open)`, exit 0.

**6. It cannot tell which lines changed** (exit 2): the same file copied outside any git repository.
```
sonar_api: precheck cannot tell which lines this change edits (git diff origin/main: error: Could not access 'origin/main'), so an "already open" finding on an edited line, which CI counts as new code, cannot be ruled out
exit=2
```

## Cleanup
Case 5's scratch clone lives in its `mktemp -d` directory, outside the repo: `rm -rf "$T"` when done (nothing is
pushed from it; its `origin` is the local checkout). After every run, success or failure, the throwaway project `weyland-lab-precheck-<pid>` is deleted and its token
revoked. Checked after the runs above:
```
python3 /home/edwardmangini/IdeaProjects/weyland/scripts/sonar_api.py projects/search q=precheck   → paging.total 0
python3 /home/edwardmangini/IdeaProjects/weyland/scripts/sonar_api.py user_tokens/search           → 0 tokens named *precheck*
```
The planted file lives in the session's scratch directory, outside the repo.
