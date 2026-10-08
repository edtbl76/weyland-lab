---
id: scan-triage
title: The code-scan triage
category: Engineering
description: Work the scan-suite findings to zero real ones, highest severity first, fixing real issues and recording an accepted reason for each false or tolerated one.
terminal_condition: Every finding at or above High is fixed, accepted in its scanner's ignore file with a written reason, or proven a false positive, and a rerun of the same scanners shows no untriaged High finding.
source: docs/runbooks/code-quality.md (B47 triage + scanner fixes; B69 weekly CronJobs + the scan-suite)
---

## Prompt

Triage the latest code-scan-suite findings for weyland-lab ({{scanner_or_all}}).

1. Read the current counts per scanner and severity (Port `security_scan`, or the scan-suite run's output; see
   `docs/runbooks/code-quality.md`). Work Critical first, then High.
2. For each finding, prove what it is before deciding:
   - a secret (gitleaks): treat as real until proven otherwise; rotate, then purge;
   - a dependency CVE: check the version actually installed (an unpinned requirement makes the scanner read 0.0.0 and
     match every CVE);
   - a manifest or code finding: read the line and the rule.
3. Decide one of: fix it, accept it in that scanner's ignore file with a one-line reason (`.trivyignore`,
   `osv-scanner.toml`, and so on), or record it as a false positive with the evidence.
4. Rerun the scanner that found it and confirm the finding is gone or accepted.

Stop when the terminal condition holds. Report the before and after counts per scanner, each fix, and each accepted
item with its reason.
