# Demo: the weekly Linear digest in Slack #linear-updates (B237)

Every Monday at 05:40 NY, Dagster reads the nightly Linear snapshot and posts a summary of the Weyland Lab board to Slack
`#linear-updates`: what closed and opened in the last 7 days, the open High lane with hold labels, and the issues
untouched for 30+ days ([runbook](../runbooks/linear-backup.md) § Weekly digest,
[flow](../diagrams/flow-linear-digest.md)). Part 1 was RUN 2026-11-07. Part 2 is the live post, after the image ships.

## 1. The logic, on the real snapshot (RUN 2026-11-07, nothing posted)

The formatter's 19 unit tests (`tests/test_linear_digest.py`, written Red first): closed / opened in the window only, the
High lane with `parked:*` holds, stale count + oldest 5, other projects never leaking in, a quiet week still sending
zeros, "+N more" with the true count kept, every section under Slack's 3,000 characters, a snapshot older than 26 h
refused, and only HTTP 200 + `ok` counted as delivered (the URL never echoed in an error).

Then the same module on the real snapshot of 2026-11-07T10:20Z, read from MinIO and built locally without posting:

| | |
|---|---|
| Snapshot age | 13.4 h (fresh) |
| Counts | closed 9, opened 1, High lane 10, stale 17 |
| Message | 6 blocks; the longest section 1,038 characters; the stale list shows the oldest 5 then "+12 more" |
| Holds | the High lane showed `[parked:held]` on EMA-195, EMA-305, EMA-323 and `[parked:deferred]` on EMA-216 |

And the Dagster wiring, loaded in the real user-code image (`weyland-dagster-user-code:git-94e2807e`, the new package
overlaid): `linear_digest_job` → `linear_weekly_digest`, schedule `40 5 * * 1` America/New_York, RUNNING by default.

## 2. The live post (RUN 2026-11-08 02:29 UTC, run `d3d50641`)

Shipped with `ship-images.sh` (`git-8498523f`: pipeline #602, PR #315 merged, Dagster and Feast answered a real
transaction). The on-demand run below: `RUN_SUCCESS` (the asset only succeeds when Slack answers `200 ok`); the owner
confirmed the message in `#linear-updates` ("It's there"). Counts, from the 2026-11-07T10:20Z snapshot: **closed 9,
opened 1, High lane 10, stale 17**, exactly what the module computes from that snapshot for the run's time. A live Linear
query for the same window read closed 10 / opened 2 / High 9 / stale 17: the differences are EMA-248 (closed) and EMA-337
(created) that evening, after the snapshot. Expected: the digest reads the snapshot by design, and the Monday run reads a
20-minute-old one.

To repeat it:

Run it now, from the runbook (it posts a real message):

[mother]
```
kubectl exec -n weyland deploy/dagster-user-code -- python3 -c "import json,urllib.request;q='mutation(\$p:ExecutionParams'+chr(33)+'){launchRun(executionParams:\$p){__typename ... on LaunchRunSuccess{run{runId}} ... on PythonError{message}}}';v={'p':{'selector':{'repositoryLocationName':'weyland_pipeline','repositoryName':'__repository__','jobName':'linear_digest_job'},'runConfigData':{}}};r=urllib.request.Request('http://dagster-webserver.weyland.svc.cluster.local:3000/graphql',data=json.dumps({'query':q,'variables':v}).encode(),headers={'Content-Type':'application/json'});print(json.load(urllib.request.urlopen(r))['data']['launchRun'])"
```

**UAT (eyes-on):**

1. Slack → `#linear-updates`: one message headed **Weekly Linear digest**, with the context line "Weyland Lab · <window> ·
   snapshot <ts>" and four sections: Closed, Opened, High lane, Stale 30+ days, each heading carrying its count.
2. Dagster (https://dagster.weyland.lab) → Runs → the `linear_digest_job` run: green; its metadata shows the snapshot,
   its age, the window and the four counts, matching the message.
3. The counts match a direct Linear query for the same window (closed and opened in project Weyland Lab, the High lane,
   stale): record both beside this run.
