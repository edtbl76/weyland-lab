# Demo — parallel CI on two agent pools (B200)

The weyland-lab pipeline runs as ten workflows (`.woodpecker/*.yml`) on two Woodpecker agent pools: mother's
(`platform`, `deliver`, `finish`) and timberback's (the four `fixtures-*` workflows and the three `golden-path-*`
shards). A full run took 89-101 minutes as one sequential workflow; it now takes about 18. Sequence diagram:
[flow-ci-workflows.md](../diagrams/flow-ci-workflows.md). Design: [arch.md §10m](../arch.md). Runbook:
[woodpecker.md § Agent pools](../runbooks/woodpecker.md).

## UI walkthrough (eyes-on UAT)

1. Open `https://woodpecker.weyland.lab/repos/2` and pick the newest full pipeline.
2. **Confirm** the left column lists ten workflows: `platform`, `fixtures-haskell`, `fixtures-a`, `fixtures-b`,
   `fixtures-c`, `golden-path-1`, `golden-path-2`, `golden-path-3`, `deliver`, `finish`.
3. **Confirm** the seven work workflows started at the same time, `deliver` started only after all of them finished,
   and `finish` last.
4. Open `finish` → `notify-port`. **Confirm** the log line `pipeline status=<success|failure> ...` lists every other
   workflow's state.

## CLI walkthrough

List the agents, their pool label and their workflow slots (the response carries each agent's token, so print only
these fields; the newest `last_contact` rows are the live agents):

[rogueone]
```
set -a && . /home/edwardmangini/IdeaProjects/weyland/scripts/.env && set +a && curl -sS -m 30 "$WOODPECKER_SERVER/api/agents?perPage=50" -H "Authorization: Bearer $WOODPECKER_TOKEN" | python3 -c 'import json,sys; [print(a["id"], a["name"], a["backend"], "capacity", a["capacity"], "labels", a["custom_labels"], "last_contact", a["last_contact"]) for a in json.load(sys.stdin) if a["backend"] == "kubernetes"]'
```

Expected (2026-11-19): `woodpecker-agent-0` and `woodpecker-agent-1` with `capacity 1 labels {'node': 'mother'}`,
and `woodpecker-agent-timberback-0` with `capacity 7 labels {'node': 'timberback'}`.

Run a smoke of ONE golden path. It exercises the sharding: shard 1 builds the path, shards 2 and 3 have nothing to
run and say so, every other workflow skips its gated steps:

[rogueone]
```
set -a && . /home/edwardmangini/IdeaProjects/weyland/scripts/.env && set +a && woodpecker-cli pipeline create edtbl76/weyland-lab --branch main --var SMOKE_ONLY=smoke --var GOLDEN_PATH_ONLY=go/gin
```

Then read each workflow's outcome (replace `<n>` with the pipeline number the create printed):

[rogueone]
```
set -a && . /home/edwardmangini/IdeaProjects/weyland/scripts/.env && set +a && curl -sS -m 20 "$WOODPECKER_SERVER/api/repos/2/pipelines/<n>" -H "Authorization: Bearer $WOODPECKER_TOKEN" | python3 -c 'import json,sys; p=json.load(sys.stdin); print(p["status"]); [print(w["name"], w["state"], [c["name"] for c in w.get("children") or [] if c["state"] == "success" and c["name"] != "clone"]) for w in sorted(p["workflows"], key=lambda w: w["name"])]'
```

Expected: `success`; `golden-path-1` ran `golden-path-smoke` and `trunk-upload` (its log: `golden-path: uploaded`);
`golden-path-2` and `golden-path-3` ran both too, and their `trunk-upload` log says `this shard had no golden path to
run, so there is nothing to upload`; the `fixtures-*` workflows ran nothing but their clone; `deliver` and `platform`
ran their ungated guards only (deliver's steps all gate on smoke); `finish` posted the status.

**Run 2026-11-19, #693:** the shards behaved exactly as above, but the pipeline FAILED: `platform`'s `trunk-upload` was
ungated, ran in smoke mode with no report (its writers skip on `SMOKE_ONLY`) and exited 2. A regression of the B200
split (step 2), found by this demo. Fixed by gating it like its writers; `scripts/tests/pipeline-layout.bats` now fails
any `trunk-upload` broader than its workflow's JUnit writers. The re-run after the fix is recorded below.

A full run for comparison (about 18 minutes): `woodpecker-cli pipeline create edtbl76/weyland-lab --branch main`.
**#692 (2026-11-19):** green in 17 min 37 s; golden-path-1/2/3 took 8.0-8.6 min each, platform 14.5, fixtures-haskell
14.8; deliver started at +14 min, finish at +17.

## Expected result

Ten workflows; the work ones in parallel across both pools; `deliver` only after a fully green set; `finish` last,
reporting the pipeline's true status to Port (and to Slack on failure).

## Cleanup / teardown

Read-only apart from the pipelines it triggers, which leave nothing running (the golden-path Jobs tear themselves
down). Nothing to clean up.
