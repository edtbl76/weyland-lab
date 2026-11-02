# Flow: SDD framework bake-off, one trial (B86)

One trial of the bake-off, from a clean repo to a judged, costed result. The non-obvious parts are the isolation (the
trial can see neither the lab repo nor the operator's config), the AI-DLC 2.11 click-through driver (it answers each
gate in a new turn, and stops on a final status), and the fail-closed judging: hidden behaviour judges, a base check
before every derived run, and stats that count a driven run only up to its first final status. Harness:
`eval/sdd-bakeoff/`; runbook [runbooks/sdd-frameworks.md](../runbooks/sdd-frameworks.md); verdict
[concepts/spec-driven-frameworks.md](../concepts/spec-driven-frameworks.md).

```mermaid
sequenceDiagram
    participant O as Operator (rogueone)
    participant H as Harness (eval/sdd-bakeoff)
    participant W as Work dir (SDD_BAKEOFF_HOME)
    participant C as Claude Code (sandboxed, fresh config, no MCP)
    participant J as Hidden judge (docker, CI image)
    O->>H: build_trials.sh then install_frameworks.sh
    H->>W: trial repo from git archive of the pre-fix commit, framework as commit 2
    O->>H: rep_job.sh task arm suffix
    H->>C: claude -p (framework lead + unattended policy), env -i, sandbox denies the lab repo
    C->>W: reads TASK.md, drives the framework, edits the trial repo
    C-->>H: stream-json result (cumulative session cost)
    alt arm is AI-DLC 2.11 (refuses a standing answer)
        loop until TRIAL DONE, a final TRIAL BLOCKED, a no-change reply, or 25 replies
            H->>C: claude -p "Yes - take the recommended option." --resume session
            C-->>H: next gate question, or a final status
        end
    end
    H->>J: judge the trial repo (read-only mount)
    J-->>H: JUDGE PASS or FAIL, by behaviour and exit codes only
    H->>W: results/replicates.tsv line (verdict + any command not found)
    opt layer 2 and the docs ablation
        H->>J: BASE_CHECK the follow-on repo before any agent runs
        J-->>H: must FAIL, a PASS means the answer is already there
        H->>C: follow-on change by plain Claude Code, framework documents kept or removed
        H->>J: judge the follow-on
    end
    O->>H: analyze.py
    H->>W: results/analysis.txt (exact stratified tests, Holm-corrected)
```

**Why this shape:**
- **Isolation over trust.** Each trial gets an `env -i` environment, a fresh `CLAUDE_CONFIG_DIR`, `--strict-mcp-config`
  with no servers, and a bubblewrap sandbox. The sandbox denies `~/IdeaProjects`, so a trial cannot read the real fix.
- **The judge never reads prose.** It runs the trial's code against hidden cases. A framework that writes a beautiful
  spec and wrong code fails.
- **The driver exists only for AI-DLC 2.11.** Every other arm gets one prompt. The driver's stop rule and the stats'
  truncation are pinned in `scripts/tests/sdd-bakeoff.bats`, because the first version over-replied 15 times on one run.
