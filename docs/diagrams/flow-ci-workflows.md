# Flow: weyland-lab CI — ten workflows on two agent pools (B200)

How one weyland-lab pipeline runs since B200 (2026-11-18/19). Woodpecker reads every `*.yml` in `.woodpecker/` as a
workflow of the same pipeline. Each workflow names its agent pool by label: an agent takes a workflow only if it carries
every label the workflow lists. mother's pool (2 agents, 1 slot each) runs `platform`, `deliver` and `finish`;
timberback's pool (1 agent, 7 slots) runs the four `fixtures-*` workflows and the three `golden-path-*` shards, all at
once. Each workflow has its own workspace, and its step pods are pinned to its pool's node, so its caches are on the same
node. `deliver` waits for every work workflow and is skipped if one failed. `finish` waits for everything and reads the
pipeline's true status from the API, because a workflow's own `$CI_PIPELINE_STATUS` sees only that workflow.
Layout and rules: `.woodpecker/README.md`. Design: [arch.md §10m](../arch.md). Runbook: [woodpecker.md](../runbooks/woodpecker.md).

```mermaid
sequenceDiagram
    participant T as trigger (woodpecker-cli or the 01:00 NY cron)
    participant S as Woodpecker server
    participant M as mother pool (node=mother, 2 slots)
    participant B as timberback pool (node=timberback, 7 slots)
    participant K as buildkitd (timberback)
    participant P as Port and Slack
    T->>S: pipeline create (optional --var RUN_FIXTURES / SMOKE_ONLY / FIXTURE_LANES)
    S->>S: read .woodpecker/*.yml into 10 workflows
    par work workflows, in parallel
        S->>M: platform (guards, production tests, integration, sonar-gate)
        S->>B: fixtures-haskell, fixtures-a, fixtures-b, fixtures-c (sample-app lanes)
        S->>B: golden-path-1, -2, -3 (one third of the golden paths each)
        B->>K: buildctl build of each golden path
        Note over M,B: step-level gates skip lanes in lean, smoke and per-lane runs
        Note over B: each workflow with lanes runs its own trunk-upload
    end
    alt every work workflow succeeded
        S->>M: deliver (detect-changes, build, kubeconform, deploy-handoff)
        M->>K: buildctl build of the changed images
    else any work workflow failed
        S->>S: skip deliver (no images from a red run)
    end
    S->>M: finish (after everything, on success or failure)
    M->>S: GET the pipeline's workflows (pipeline-status.sh, anonymous read)
    S-->>M: each workflow's state
    M->>P: notify-port posts the true status, notify-slack only on failure
    Note over M,P: unknown status (a workflow still running, an unreadable API) is reported as failure
```

Last proven 2026-11-19: full CI #692 green in 17 min 37 s, all seven timberback workflows at once. CI #689/#690 failed
in one workflow each: `deliver` was skipped and `finish` posted `failure` to Port and Slack.
