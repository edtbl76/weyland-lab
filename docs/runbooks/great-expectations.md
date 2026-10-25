# Great Expectations — runbook (B77 part b)

The third data-quality source: Great Expectations 0.18 auto-profiles the showcase tables, validates them, and
publishes DataHub Assertions (next to Soda and the `@asset_check` gate) plus Data Docs at `https://ge-docs.weyland.lab`.
How it works and what it shows: [demos/great-expectations.md](../demos/great-expectations.md). This runbook (added
2026-10-25, B227 follow-on: GE had a demo but no runbook) holds the commands.

| Piece | Where |
|---|---|
| Runner | `services/weyland-dagster/ge/ge_validate.py`, run by the isolated `/opt/ge-venv` in the user-code image |
| Lockfile | `services/weyland-dagster/requirements-ge.txt` (its own venv: GE's pins clash with the main env) |
| Job | `ge_validate_job` (on demand, no schedule; advisory: a failing expectation never fails the job) |
| Context | a FILE context on the `ge-data` PVC (`/ge-data`), so suites and results outlive every run |
| Tests | `services/weyland-dagster/tests/test_ge_validate.py` |

## Run it on demand

[mother]
```
kubectl exec -n weyland deploy/dagster-user-code -- python3 -c "import json,urllib.request;q='mutation(\$p:ExecutionParams!){launchRun(executionParams:\$p){__typename ... on LaunchRunSuccess{run{runId}} ... on PythonError{message}}}';v={'p':{'selector':{'repositoryLocationName':'weyland_pipeline','repositoryName':'__repository__','jobName':'ge_validate_job'},'runConfigData':{}}};r=urllib.request.Request('http://dagster-webserver.weyland.svc.cluster.local:3000/graphql',data=json.dumps({'query':q,'variables':v}).encode(),headers={'Content-Type':'application/json'});print(json.load(urllib.request.urlopen(r))['data']['launchRun'])"
```
Then read the run's `ge_validate_op` log (Dagster UI → Runs). A healthy run prints one line per table,
`<table>: N expectations profiled, checkpoint success=...`, then `wrote /tmp/ge_results.json (3 datasets)`.
`GE runner exit 1 — advisory` means the runner itself failed: read the traceback above it.

## The rerun fix (2026-10-25)

Every run after the first had died on its first table: `ExpectationSuiteError: An ExpectationSuite named
ge_iceberg_dbt_mart_country_health already exists`. The runner created each suite with
`get_validator(create_expectation_suite_with_name=...)`, which refuses an existing suite, and the context is a file on
the PVC, so the suite from the last run was always there. `suite_validator()` now resets the suite to empty
(`add_or_update_expectation_suite`) and attaches the validator to it, so each run re-profiles the table as it is now.

## Tests

The tests need GE, which the CI Python lane does not install, so there they skip (collected with weyland-dagster's
other tests). Run them for real in the GE venv:

[rogueone]
```
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/services/weyland-dagster:/src:ro python:3.11-slim sh -c 'python -m venv /tmp/ge && /tmp/ge/bin/pip install -q -r /src/requirements-ge.txt pytest && cd /src && /tmp/ge/bin/python -m pytest -q -p no:cacheprovider tests/test_ge_validate.py'
```
Expect `2 passed`: one pins the bug (GE's create-only call fails on a rerun), one proves the runner re-profiles on
every run without piling up expectations.
