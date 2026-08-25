# Demo — Port PR entity reconciliation (B144)

Reaping `githubPullRequest` entities whose pull request has closed. **Executed + eyes-on 2026-08-25** (✅) —
dry run, live run, and the post-reap verification are all real output below, not written from memory.

- **runbook:** [runbooks/pr-lifecycle.md](../runbooks/pr-lifecycle.md) § Reaping stale Port PR entities
- **Flow:** [diagrams/flow-port-pr-reconcile.md](../diagrams/flow-port-pr-reconcile.md)

**What it fixes:** `github-weyland` fetches **only open PRs**. A PR that closes stops appearing in the
source data, and an incremental sync upserts but never deletes — so the entity survives forever claiming
`status: open`. Those entities feed `service/dora_lead_time` and `service/delivery_performance`, so a PR
that closed weeks ago inflates cycle time permanently and the scorecard degrades with age.

## UI walkthrough (eyes-on)

1. **Port → Catalog → Pull Requests** — `https://app.port.io` → Catalog → `githubPullRequest`.
   **UAT — confirm:**
   - The entity count matches what GitHub actually has open. As of 2026-08-25 that is **7**.
   - Every row shows `status: open` **and** has a `closedAt` of `null`. A row with `status: open` and a
     populated `closedAt` would mean the mapping changed; a row for a PR you know is merged means the
     reaper has not run since.
   - Spot-check one against GitHub — click through the `link` property and confirm the PR is genuinely
     open. Before B144, `weyland-lab#36` sat here for a day reading `open` while merged.
2. **Port → Scorecards → `service/dora_lead_time`** — the consumer that was being corrupted.
   **UAT:** note the current value. It is only trustworthy once the entity count matches GitHub; a stale
   open PR is indistinguishable from a genuinely long-running one from inside the scorecard.
3. **Grafana → Alerting** — confirm `ScheduledJobFailed` covers `port-pr-reconcile`.
   **UAT:** the rule's `job_name` regex must contain `port-pr-reconcile`. This job fails **closed**, so a
   broken run exits non-zero having reaped nothing while the catalog keeps accumulating — freshness alone
   would stay quiet as long as a later run succeeded.

## CLI walkthrough (the test — RUN against live infra)

**1. Extract the logic the cluster actually runs.** It lives in a ConfigMap so the bats suite and the
CronJob execute the same text.

```
cd nodes/mother/lab/weyland-platform/k8s/pr-lifecycle && awk -v key="port-pr-reconcile.sh" '$0 ~ "^  " key ": \\|" {g=1;next} g && !/^    / && !/^[ \t]*$/ {g=0} g {sub(/^    /,"");print}' port-pr-reconcile.yaml > /tmp/reap.sh && wc -l /tmp/reap.sh
```

Expect `186 /tmp/reap.sh`. If it is 0 lines, the ConfigMap key changed — every later step would then pass
vacuously against an empty file, which is what the suite's first test exists to catch.

**2. Dry run — always first.** Reports what it would reap and touches nothing.

```
cd nodes/mother/lab/weyland-platform/k8s/pr-lifecycle && set -a && . ../../tofu/port/.env && set +a && export GITHUB_TOKEN="$(gh auth token)" && PORT_REAP_DRY_RUN=1 sh /tmp/reap.sh
```

With a stale entity present (2026-08-25, before the first live run):

```
fetched the open PR entity list from Port successfully
check entity 4240999487 = midi_real_book#3 github_state=open
check entity 3988747022 = stud.io#110 github_state=open
check entity 4345412397 = weyland-lab#36 github_state=closed
  -> would reap 4345412397 (weyland-lab#36 is closed)
check entity 4124755477 = midi_real_book#1 github_state=open
check entity 4080763548 = stud.io#116 github_state=open
check entity 4148749500 = midi_real_book#2 github_state=open
check entity 4245570001 = emangini-tailwind-nextjs-contentlayer#91 github_state=open
check entity 4258787100 = stud.io#121 github_state=open
done - 8 open PR entities checked, 1 reaped
```

Steady state, same day, after the reap:

```
done - 7 open PR entities checked, 0 reaped
```

**Both are exit 0, and they are not the same result.** The job says which it was — `N checked` is what
distinguishes "nothing to do" from "could not see anything", and a run that skipped any entity exits
non-zero regardless.

**3. Reap for real.** Drop the dry-run flag. Back the entity up first — the integration will **not**
recreate it, because it only ever fetches open PRs:

```
cd nodes/mother/lab/weyland-platform/tofu/port && set -a && . ./.env && set +a && TOK=$(curl -sS -X POST https://api.port.io/v1/auth/access_token -H 'Content-Type: application/json' -d "{\"clientId\":\"$PORT_CLIENT_ID\",\"clientSecret\":\"$PORT_CLIENT_SECRET\"}" | python3 -c 'import sys,json;print(json.load(sys.stdin)["accessToken"])') && curl -sS "https://api.port.io/v1/blueprints/githubPullRequest/entities/<ID>" -H "Authorization: Bearer $TOK" > /tmp/entity-<ID>-backup.json
```

**4. THE acceptance — compare the two systems, not the exit code.**

```
cd nodes/mother/lab/weyland-platform/tofu/port && set -a && . ./.env && set +a && TOK=$(curl -sS -X POST https://api.port.io/v1/auth/access_token -H 'Content-Type: application/json' -d "{\"clientId\":\"$PORT_CLIENT_ID\",\"clientSecret\":\"$PORT_CLIENT_SECRET\"}" | python3 -c 'import sys,json;print(json.load(sys.stdin)["accessToken"])') && PORT_N=$(curl -sS "https://api.port.io/v1/blueprints/githubPullRequest/entities" -H "Authorization: Bearer $TOK" | python3 -c 'import sys,json;print(len(json.load(sys.stdin)["entities"]))') && GH_N=0 && for r in weyland-lab stud.io midi_real_book Algopedia ServiceTransformation emangini-tailwind-nextjs-contentlayer; do n=$(gh pr list --repo "edtbl76/$r" --state open --json number --jq 'length') || exit 1; GH_N=$((GH_N+n)); done && echo "port=$PORT_N github=$GH_N" && [ "$PORT_N" -eq "$GH_N" ] && echo "MATCH"
```

```
port=7 github=7
MATCH
```

That is the B144 acceptance, and it is the first time the two systems have agreed since the ship loop
started producing tag-bump PRs.

**5. The tests, including the ones that prove it refuses to delete.**

```
docker run --rm -v "$PWD:/code:ro" -w /code --entrypoint sh bats/bats:latest -c 'apk add --no-cache jq >/dev/null 2>&1; bats scripts/tests/port-pr-reconcile.bats'
```

Expect **19 ok**. The majority assert that nothing was deleted — GitHub unreachable, an empty state, an
unrecognised state, a missing `prNumber`, a missing `repository` relation, absent credentials. The
weighting matches the risk: this is the only job in `pr-lifecycle/` whose worst failure destroys data.

## Teardown

**Steps 1, 2, 4 and 5 are read-only** — they extract a file, issue `GET`s, and run tests in a container.

**Step 3 deletes catalog entities and the integration will not recreate them.** That is the job's purpose,
not an accident, but it is genuinely destructive. Restore one from the backup taken in step 3:

```
cd nodes/mother/lab/weyland-platform/tofu/port && set -a && . ./.env && set +a && TOK=$(curl -sS -X POST https://api.port.io/v1/auth/access_token -H 'Content-Type: application/json' -d "{\"clientId\":\"$PORT_CLIENT_ID\",\"clientSecret\":\"$PORT_CLIENT_SECRET\"}" | python3 -c 'import sys,json;print(json.load(sys.stdin)["accessToken"])') && python3 -c "import json;d=json.load(open('/tmp/entity-<ID>-backup.json'))['entity'];print(json.dumps({k:d[k] for k in ('identifier','title','properties','relations')}))" | curl -sS -X POST "https://api.port.io/v1/blueprints/githubPullRequest/entities?upsert=true" -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' -d @-
```

Cleanup: `rm -f /tmp/reap.sh /tmp/entity-*-backup.json`.
