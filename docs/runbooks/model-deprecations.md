# Anthropic model deprecations (B223)

A retired Claude model fails every request sent to it, so a config that still names one is an outage with a date on
it. Anthropic emails at least 60 days ahead. On 2026-10-18 a Claude Haiku 3.5 email took four manual checks (git
history, the MLflow gateway, Bifrost, the key-rotation log) to establish that nothing here used it. Two checks now
answer that question, and they fail on their own if the answer changes.

| Check | What it reads | When | Fails on |
|---|---|---|---|
| **Repo guard** `scripts/check-model-deprecations.sh` | every Anthropic model ID in config and code in git | CI `repo-guards`, every build | a retired model, or one retiring within 30 days, named `file:line` with its replacement |
| **Live check** CronJob `anthropic-model-watch` (`k8s/bifrost/anthropic-model-watch.yaml`) | the MLflow AI Gateway's model definitions; Bifrost's Anthropic key and virtual-key model lists; Anthropic's `GET /v1/models` with Bifrost's key | daily 03:55 NY | the same, plus any ID the API no longer offers, so a retirement not yet copied into the manifest still fails |

Both read **`scripts/anthropic-models.json`**: every row of the "Model status" and "Deprecation history" tables on
Anthropic's [model deprecations page](https://platform.claude.com/docs/en/about-claude/model-deprecations). The logic
is `scripts/model_lifecycle.py`, the same file in both places: the CronJob embeds it byte for byte, and a bats test
fails CI if the two copies differ.

**Verdicts.** FAIL: retired, or deprecated with the retirement date within 30 days (`fail_within_days`). WARN:
deprecated with more time or no date yet, or an ID the manifest does not list (a new model, or a typo). Every
spelling of one model counts as the same model. `claude-haiku-4-5`, `claude-haiku-4-5-20251001`,
`anthropic/claude-haiku-4-5`, `openai/anthropic/claude-haiku-4-5` and Bifrost's display name `claude-4.5-haiku` all
resolve to the one dated entry.

**Exit codes** (both checks): `0` clean · `1` a retired, retiring or unoffered model is in use · `2` **could not
check**: no or malformed manifest, nothing scanned, a live source unreadable, or the API listed no models. A `2` is
never a pass. The CronJob fails on `1` and on `2`, and `ScheduledJobFailed` pages.

**Not scanned, deliberately:** `docs/`, `docs/backlog.md` history, `*.md`, tests (`tests/`, `test_*.py`, `*.bats`),
notebook outputs (only code cells are read, so a cell that printed LiteLLM's passthrough list is not a use), and
`.claude/`. That last one is the vendored AI-DLC framework, whose Amazon Bedrock IDs follow Bedrock's own
retirement schedule, not the Claude API's. OpenAI and other providers are out of scope until this approach has
proven itself on Anthropic.

## When a deprecation email arrives

1. **Update the manifest from the source page.** Open the deprecations page. In `scripts/anthropic-models.json`,
   change the model's `state` to `deprecated`, add `deprecated`, `retires` and `replacement` (dates as
   `YYYY-MM-DD`), add any new models, and set `checked` to today. Copy the page; never type the dates from the email.
2. **Re-embed it into the CronJob** (the bats test fails CI until you do):
   [rogueone]
   ```
   bash /home/edwardmangini/IdeaProjects/weyland/scripts/embed-anthropic-model-watch.sh
   ```
3. **Find every use in git:**
   [rogueone]
   ```
   bash /home/edwardmangini/IdeaProjects/weyland/scripts/check-model-deprecations.sh
   ```
   A retirement more than 30 days out prints `WARN path:line`. Inside 30 days it prints `FAIL`, and CI blocks the build.
4. **Move each use to the replacement** the manifest names, in git. Git is the source of truth for the MLflow gateway's
   models (`nodes/mother/lab/weyland-platform/scripts/register_gateway_endpoints.py`, then re-run it as its docstring
   says), for LiteLLM (`k8s/litellm/configmap.yaml`), and for every other config file the guard names.
5. **Prove the running gateways are clean.** After the push and the Argo sync, run the live check on demand. Don't
   wait for 03:55:
   ```
   J=anthropic-model-watch-manual-$(date +%s); kubectl -n weyland create job --from=cronjob/anthropic-model-watch "$J" && kubectl -n weyland wait --for=jsonpath='{.status.conditions[0].status}'=True --timeout=180s job/"$J"; kubectl -n weyland get job "$J" -o jsonpath='succeeded={.status.succeeded} failed={.status.failed}{"\n"}' && kubectl -n weyland logs job/"$J" --tail=20
   ```
   Expect `succeeded=1 failed=`, then one `OK` line per Anthropic model the gateways hold, then the summary line. `failed=1`
   means read the `FAIL` or `CANNOT CHECK` lines (below).

Bifrost's key and virtual keys allow `*` today (any model, none named), so its rows come from the live listing.
Pinning a specific Anthropic model in Bifrost adds it to the check automatically.

## Reading a failure

| Output | Meaning | Do |
|---|---|---|
| `FAIL path:line <id> -> <id> retired <date>; replacement <r>` | git names a retired model | move it to `<r>` (step 4) |
| `FAIL … retires <date> — N day(s) left` | retiring within 30 days | the same, now |
| `FAIL mlflow <def>: <id> -> not offered by GET /v1/models` | the API stopped offering a model the gateway still uses, and the manifest may not know yet | update the manifest (step 1), then migrate (step 4) |
| `WARN … not in the manifest` | a model newer than the manifest, or a typo | check the page; add it, or fix the ID |
| `WARN the manifest was last checked <date> (over 90 days)` | the manifest is stale | re-read the page (step 1) |
| `CANNOT CHECK: mlflow: unreachable` / `HTTP 4xx` | the source could not be read; this is not a pass | MLflow's front-door policy must admit `app: anthropic-model-watch` (`k8s/mlflow/netpol.yaml`) |
| `CANNOT CHECK: bifrost_keys: HTTP 401` | the setup token was rejected | `bifrost-setup-token` Secret (`mcp-gateway.md`) |
| `CANNOT CHECK: anthropic: HTTP 401` / `listed no models` | Bifrost's Anthropic key is revoked or wrong | `bifrost-provider-keys` (`secrets-map.md`); the key rotation runbook |

As of 2026-10-19 the lab uses one Anthropic model, `claude-haiku-4-5-20251001`: Active, with a "not sooner than"
date of 2026-10-15. That date has passed, so its deprecation notice can come at any time. Its manifest replacement
row is the one to watch.
