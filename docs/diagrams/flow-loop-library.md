# Flow: the loop library, from git to Bifrost (B175)

The lab's reusable agent loops live in git (`knowledge-repos/loop-library/`, one Markdown file per loop, each with a
terminal condition) and are published to Bifrost's Prompt Repository so every harness can find them. The Dagster
image cannot read `knowledge-repos/`, so a generated bundle travels inside the image, and CI fails while the bundle is
stale. Git always wins: a changed loop becomes a new Bifrost version, an unchanged one posts nothing, and a loop
removed from git is reported, not deleted. See [knowledge-repos/loop-library/README.md](../../knowledge-repos/loop-library/README.md),
[demos/loop-library.md](../demos/loop-library.md), [runbooks/prompt-federation.md](../runbooks/prompt-federation.md).

```mermaid
sequenceDiagram
    participant A as author (owner or agent)
    participant G as git (knowledge-repos/loop-library)
    participant E as embed-loops.sh
    participant CI as CI repo-guards (check-loop-library.sh)
    participant IMG as dagster-user-code image (scripts/loop_library.json)
    participant DG as Dagster registrations (weekly Sun 05:00)
    participant BF as Bifrost Prompt Repository (folder loop-library)
    participant FED as prompt federation (Langfuse + MLflow mirror)
    A->>G: edit or add a loop (frontmatter + Prompt section)
    A->>E: bash scripts/embed-loops.sh
    E->>G: validate every loop, then write the bundle
    G->>CI: push
    CI->>CI: every loop has a checkable terminal condition, bundle byte-identical to a fresh one
    alt invalid loop or stale bundle
        CI-->>A: exit 1 names the loop or says re-embed
    else valid and in sync
        CI->>IMG: build ships the image with the bundle
        DG->>IMG: bifrost_loops_registered runs register_bifrost_loops.py
        IMG->>BF: GET folders, prompts (limit=1000), each prompt's latest version
        alt loop new
            IMG->>BF: create prompt loop-id + first version
        else text differs from git
            IMG->>BF: new version (git wins)
        else unchanged
            Note over IMG,BF: nothing posted
        end
        Note over IMG,BF: a loop-* prompt no longer in git is reported as an orphan, never deleted
        DG->>FED: prompt_federation_synced runs after the loops asset
        FED->>BF: mirror out to Langfuse and MLflow
    end
```
