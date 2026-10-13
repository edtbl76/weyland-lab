# API lifecycle — check, re-lock, and answer drift (B155 · B208)

Every published API is catalogued (owner, kind, status, version, contract snapshot) and its contract is locked, so a
change can't land silently. Concept and the breaking-change rules: [concepts/api-lifecycle.md](../concepts/api-lifecycle.md);
demo: [demos/api-lifecycle.md](../demos/api-lifecycle.md); flow: [flow-api-lifecycle.md](../diagrams/flow-api-lifecycle.md).

| Piece | Where |
|---|---|
| Catalog | `nodes/mother/lab/weyland-platform/services/weyland-dagster/weyland_pipeline/apis.yaml` |
| Contract snapshots + lock | `docs/api/specs/*.openapi.json`, `*.a2a-card.json`, `docs/api/specs/contract-lock.json` |
| PR-time guard | `scripts/check-api-lifecycle.sh` (CI `repo-guards`) |
| Breaking-change engine | `scripts/lib/api_spec_diff.py` |
| Live drift check | `scripts/lib/api_drift.py`, run nightly by the `api-drift` CronJob (03:20 NY, ns `monitoring`) |

All commands run on **rogueone** from the repo root unless marked `[mother]`.

## Check the catalog and the lock

```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/check-api-lifecycle.sh
```
Exit 0 = every published API is catalogued, snapshotted and locked; 1 = a finding (named); 2 = could not run.

## Re-lock after a contract change

When an API's contract changes, refresh its snapshot (below), then:
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/gen-api-contract-lock.sh
```
An additive change re-locks freely. A **breaking** change is refused (exit 1, named) unless the API's MAJOR version
was bumped in `apis.yaml`. Then run `scripts/embed-api-drift.sh`, because the drift CronJob carries its own copy of
every snapshot (`api-drift.bats` checks they're identical).

## Refresh a snapshot

**From the code** (a change that isn't deployed yet, as in B207). For a FastAPI service whose tests stub its
heavy clients in `conftest.py`, generate the spec from the app in its test environment, keys sorted (the committed
files are sorted, so the diff shows only the real change):
```
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -e PIP_USER=1 -e PYTHONUSERBASE=/tmp/pu -e PATH=/tmp/pu/bin:/usr/local/bin:/usr/bin:/bin -v /home/edwardmangini/IdeaProjects/weyland:/w -w /w/nodes/mother/lab/weyland-platform/services/<service> python:3.12-slim sh -c 'pip install -q -r requirements-test.txt pytest >/dev/null 2>&1 && python -c "import sys, json; sys.path.insert(0, \".\"); import conftest, main; json.dump(main.app.openapi(), open(\"/w/docs/api/specs/<service>.openapi.json\", \"w\"), indent=2, sort_keys=True)"'
```
Check `git diff -- docs/api/specs/` shows only the change you meant.

**From the live service** (what the drift job compares against), from any meshed pod in `weyland`:

[mother]
```
kubectl -n weyland exec deploy/weyland-agent -c weyland-agent -- python -c "import urllib.request; print(urllib.request.urlopen('<spec_source from apis.yaml>').read().decode())" > /tmp/<api>.json
```
Copy it to rogueone, re-serialise with `sort_keys=True` over the snapshot, and re-lock.

## The nightly drift check, and what each result means

Each catalogued API with a `spec_source` is fetched live and compared with its snapshot:

| Result | Meaning | What happens | What to do |
|---|---|---|---|
| **identical** | live == snapshot (for an A2A card, ignoring its host-derived `url` fields) | nothing | nothing |
| **ADDITIVE DRIFT** | differs, nothing breaking (a new route, an optional field, a newly documented response) | a `warning` **ApiContractStale** alert per API → Telegram, re-sent each night until fixed | refresh the snapshot and re-lock (above) |
| **BREAKING DRIFT** | a route removed, a field dropped, a new required field… | exit 1 → the job fails → `ScheduledJobFailed` | bump the MAJOR version, re-capture, migrate consumers, or revert the API change |
| **SKIP** | the source was unreachable (a scaled-down service) | listed, not alerted | nothing, unless it should be up |

Exit 2 means it could not run: the catalog or a snapshot is unreadable, or **drift was found but the alert could not
be sent** (`ALERTMANAGER_URL` unset or Alertmanager unreachable). A finding nobody hears is not reported, so that fails
the job. Before B208 (2026-10-13), additive drift passed as "match": the tool-server served an optional `langfuse`
field for two weeks that its snapshot lacked.

Run the check now instead of waiting for 03:20:

[mother]
```
kubectl -n monitoring create job api-drift-manual-$(date +%s) --from=cronjob/api-drift
```
Then `kubectl -n monitoring logs job/<that name>`: the last line is `OK — no breaking drift: N identical, N additive
drift, N skipped …`, or `BREAKING DRIFT …` / `CANNOT REPORT …`.
