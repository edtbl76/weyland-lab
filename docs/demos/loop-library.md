# Demo: the loop library (B175)

The lab's recurring agent workflows, each written once with an explicit terminal condition, kept in git and
published to Bifrost's Prompt Repository. Format and commands: [knowledge-repos/loop-library/README.md](../../knowledge-repos/loop-library/README.md).
The CLI part was RUN on 2026-10-08 on rogueone.

## Sequence diagram
See [../diagrams/flow-loop-library.md](../diagrams/flow-loop-library.md).

## CLI walkthrough

**1. Validate the library.** This is also a CI `repo-guards` step:
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/check-loop-library.sh
```
```
OK — 11 loop(s), each with a terminal condition.
loop-library: bundle in sync (…/services/weyland-dagster/scripts/loop_library.json)
```

**2. Negative: a loop without a terminal condition fails by name, exit 1.** From `scripts/tests/loop-library.bats`:
deleting `terminal_condition:` from a loop gives `INVALID ci-watch.md: missing terminal_condition`. The other cases:
- editing a loop without re-embedding prints `bundle is stale … run: bash scripts/embed-loops.sh` (exit 1);
- an empty library is exit 2, never valid;
- `embed-loops.sh` refuses to write a bundle from an invalid library.

All 7 bats cases pass in CI's `bats/bats` image.

**3. Dry run of the publisher against the live Bifrost.** Real reads; every write was recorded instead of sent:
```
live prompt count: unpaged 269 / default 269
folder  CREATED loop-library
prompt  CREATED loop-library/loop-ci-watch
… (11 loops)
DRY summary {'created': 11, 'updated': 0, 'unchanged': 0, 'failed': 0, 'orphans': []} posts that WOULD be sent: 23
```

**4. Dagster still loads with the new asset.** The live `dagster-user-code` image with the new code mounted:
`assets 154 loops asset present: True`, `job ok registrations_reconcile_job`, `bundle loops 11`.

**5. Publish for real** (after the image ships). Run the registrations job on demand in Dagster, or by hand:
```
kubectl -n weyland exec deploy/dagster-user-code -- env BIFROST_URL=http://bifrost.weyland.svc.cluster.local:8080 python /app/scripts/register_bifrost_loops.py
```
RUN 2026-10-08 on the shipped image `weyland-dagster-user-code:git-26bd0d33`:
```
folder  CREATED loop-library
prompt  CREATED loop-library/loop-ci-watch
… (11 loops)
done. 11 created, 0 updated, 0 unchanged, 0 failed, 0 orphan(s). 11 loops in git.
```
The re-run printed `0 created, 0 updated, 11 unchanged`, so it posts nothing when git and Bifrost agree. A read-back
compared every published prompt's latest version with the git text: 11 of 11 identical.

## UI walkthrough (UAT, eyes on) — DONE 2026-10-08 (owner)
1. **Bifrost:** open the Prompt Repository, then the **loop-library** folder. Eleven `loop-*` prompts are listed. Open
   `loop-ci-watch`: the text starts with the title, then `Stop when:`, then the full prompt.
2. **Langfuse:** after the same reconcile, the prompt federation mirrors the loops (`loop-*` prompts).

## Expected result
- Every loop in git is in Bifrost with the same text. A changed loop gets a new version on the next weekly reconcile.
- A loop without a checkable terminal condition, or a stale bundle, fails CI by name.

## Cleanup / teardown
Nothing to clean up. A retired loop is deleted from git, the publisher then reports it as an orphan, and it is removed
by hand in the Bifrost UI.
