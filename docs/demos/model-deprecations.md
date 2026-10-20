# Demo — Anthropic model deprecations (B223)

**What it shows.** Nothing in the lab can name a retired Claude model without something failing: CI, if git names it;
the nightly `anthropic-model-watch` Job, if a gateway's own database names it. Both read one manifest copied from
Anthropic's deprecations page. Every spelling of a model counts as the same model: `claude-haiku-4-5`,
`anthropic/claude-4.5-haiku` and the dated `claude-haiku-4-5-20251001` are one model. Flow:
[flow-model-deprecations](../diagrams/flow-model-deprecations.md). Runbook:
[model-deprecations.md](../runbooks/model-deprecations.md).

## CLI walkthrough

**1. The repo guard passes on today's tree, and says what it read.**

[rogueone]
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/check-model-deprecations.sh
```
Expect exit 0: `model-deprecations: OK — 7 Anthropic model reference(s) in <N> file(s); none retired or retiring within
30 days (0 warning(s); manifest checked 2026-10-19).` All seven are Haiku 4.5 in four spellings: four in
`k8s/litellm/configmap.yaml` (including Bifrost's display name `claude-4.5-haiku` in a comment), then
`register_gateway_endpoints.py`, `validate_bifrost_tool_calling.py` and `scripts/.env.example`.

**2. The negative: a config naming Claude Haiku 3.5 (retired 2026-02-19) fails, by file and line.**

[rogueone]
```
D=$(mktemp -d) && mkdir -p "$D/k8s" && printf 'model: claude-3-5-haiku-20241022\n' > "$D/k8s/c.yaml" && SCAN_ROOT="$D" bash /home/edwardmangini/IdeaProjects/weyland/scripts/check-model-deprecations.sh; echo "exit=$?"; rm -r "$D"
```
Expect `FAIL k8s/c.yaml:1  claude-3-5-haiku-20241022 -> claude-3-5-haiku-20241022 retired 2026-02-19; replacement
claude-haiku-4-5-20251001`, then `model-deprecations: FAIL — 1 reference(s) …` and `exit=1`.

**3. Retiring soon fails; retiring later only warns.** Claude Sonnet 4.5 is deprecated, retiring 2026-11-30. With the
clock set to 2026-11-05 (25 days out) it fails. On 2026-10-19 (42 days out) it warns.

[rogueone]
```
D=$(mktemp -d) && printf 'model: claude-sonnet-4-5-20250929\n' > "$D/c.yaml" && SCAN_ROOT="$D" MODEL_GUARD_TODAY=2026-11-05 bash /home/edwardmangini/IdeaProjects/weyland/scripts/check-model-deprecations.sh; echo "exit=$?"; SCAN_ROOT="$D" MODEL_GUARD_TODAY=2026-10-19 bash /home/edwardmangini/IdeaProjects/weyland/scripts/check-model-deprecations.sh; echo "exit=$?"; rm -r "$D"
```
Expect `… retires 2026-11-30 — 25 day(s) left; replacement claude-sonnet-5-5` and `exit=1`. Then
`WARN c.yaml:1 … deprecated 2026-09-30, retires 2026-11-30` and `exit=0`.

**4. The live check, on demand, against the running gateways.**

[mother]
```
J=anthropic-model-watch-manual-$(date +%s); kubectl -n weyland create job --from=cronjob/anthropic-model-watch "$J" && kubectl -n weyland wait --for=jsonpath='{.status.conditions[0].status}'=True --timeout=180s job/"$J"; kubectl -n weyland get job "$J" -o jsonpath='{.status.conditions[0].type}{"\n"}' && kubectl -n weyland logs job/"$J" --tail=20
```
Expect `Complete`, then `OK   mlflow anthropic-claude-haiku-4-5-md: claude-haiku-4-5 -> claude-haiku-4-5-20251001
active (not before 2026-10-15)`, then `1 Anthropic model reference(s) in the running gateways (MLflow + Bifrost; `*`
names none); 14 model(s) offered by the API`.

## UI walkthrough

- **Woodpecker** — `https://woodpecker.weyland.lab/repos/2`: open the latest pipeline, step
  **repo-guards**. **UAT:** the log shows the `model-deprecations: OK — 7 Anthropic model reference(s) …` line, and the
  step is green.
- **Argo CD** — `https://argocd.weyland.lab/applications/argocd/bifrost`. **UAT:** the app tree shows CronJob
  `anthropic-model-watch` and ConfigMap `anthropic-model-watch-logic`, both Synced and Healthy. After step 4, the
  manual Job appears under the CronJob with a completed pod.
- **Grafana alert rules** — `https://grafana.weyland.lab/alerting/list`, search `ScheduledJobFailed`. **UAT:** the
  rule's query names `anthropic-model-watch` in its `job_name` regex, and it is Normal, not Firing.

## RUN

**2026-10-19, repo side (before the push):**
- **Step 1:** exit 0, `7 Anthropic model reference(s) in 1861 file(s)`, 0 warnings.
- **Step 2:** `FAIL k8s/c.yaml:1 … retired 2026-02-19; replacement claude-haiku-4-5-20251001`, exit 1.
- **Step 3:** covered by the bats suite `scripts/tests/model-deprecations.bats`, 8/8 in the CI `bats/bats` image.
- **Tests:** `test_model_lifecycle.py` 57/57. The CI Python lane passes, and coverage for `scripts/` rose from 69% to 90%.
- **Live logic against the real sources:** MLflow through its NodePort, Bifrost read inside its pod, and Anthropic
  `GET /v1/models`. Result: `OK mlflow anthropic-claude-haiku-4-5-md: claude-haiku-4-5 -> claude-haiku-4-5-20251001
  active`; 14 models offered; exit 0.

**In-cluster (step 4, after the push):** pending the push.
