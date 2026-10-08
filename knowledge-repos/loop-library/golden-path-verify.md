---
id: golden-path-verify
title: The golden-path verify
category: Engineering
description: Prove every golden-path template still builds, starts and answers its smoke check, and fix or report the ones that do not.
terminal_condition: Every golden path in the run prints SMOKE OK, or each failing path is named with the log line that shows why and either fixed and re-run green or reported to the owner.
source: docs/design/golden-paths.md (Ephemeral-Job harness), scripts/run-golden-path-jobs.sh
---

## Prompt

Verify the golden paths ({{paths_or_all}}).

1. Run the harness described in `docs/design/golden-paths.md` (`scripts/run-golden-path-jobs.sh`, which the CI step
   `golden-path-smoke` also runs). Each path builds its image, runs it as a short Kubernetes Job, and checks `/ready`
   and `/hello`.
2. Read each path's result line. `SMOKE OK` is a pass; anything else is a fail, including a build that never
   finished.
3. For each failure, find the first error in its build or Job log. Reproduce the build locally in Docker as the
   invoking user. Fix it in the path's directory and re-run only that path.
4. A path that cannot be fixed in this pass (an upstream image gone, a toolchain bug): report it with the log line
   and the suspected cause.

Stop when the terminal condition holds. Report passed and failed counts and every fix.
