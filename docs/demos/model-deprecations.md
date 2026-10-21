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


```
J=anthropic-model-watch-manual-$(date +%s); kubectl -n weyland create job --from=cronjob/anthropic-model-watch "$J" && kubectl -n weyland wait --for=jsonpath='{.status.conditions[0].status}'=True --timeout=180s job/"$J"; kubectl -n weyland get job "$J" -o jsonpath='succeeded={.status.succeeded} failed={.status.failed}{"\n"}' && kubectl -n weyland logs job/"$J" --tail=20
```
Expect `succeeded=1 failed=`, then `OK   mlflow anthropic-claude-haiku-4-5-md: claude-haiku-4-5 -> claude-haiku-4-5-20251001
active (not before 2026-10-15)`, then `1 Anthropic model reference(s) in the running gateways (MLflow + Bifrost; `*`
names none); 14 model(s) offered by the API`.

**4b. The live check FAILS on a retired model** (the negative, live — a one-off Job with a manifest copy that marks
Claude Haiku 4.5 retired, mounted over `MODEL_MANIFEST`; it is deleted as soon as it fails, so no `KubeJobFailed`):
```
T=$(mktemp -d) && python3 -c "import json,sys;d=json.load(open('/home/edwardmangini/IdeaProjects/weyland/scripts/anthropic-models.json'));[r.clear() or r.update(id='claude-haiku-4-5-20251001',state='retired',deprecated='2026-08-01',retires='2026-10-01',replacement='claude-haiku-5-0') for r in d['models'] if r['id']=='claude-haiku-4-5-20251001'];json.dump(d,open(sys.argv[1],'w'))" "$T/m.json" && kubectl -n weyland create configmap model-watch-neg --from-file=anthropic-models.json="$T/m.json" && kubectl -n weyland create job model-watch-neg --from=cronjob/anthropic-model-watch --dry-run=client -o json | python3 -c "import json,sys;j=json.load(sys.stdin);s=j['spec'];s['backoffLimit']=0;p=s['template']['spec'];c=p['containers'][0];c['env']=[e for e in c['env'] if e['name']!='MODEL_MANIFEST']+[{'name':'MODEL_MANIFEST','value':'/opt/neg/anthropic-models.json'}];c['volumeMounts']=c.get('volumeMounts',[])+[{'name':'neg','mountPath':'/opt/neg','readOnly':True}];p['volumes']=p.get('volumes',[])+[{'name':'neg','configMap':{'name':'model-watch-neg'}}];print(json.dumps(j))" | kubectl create -f - && kubectl -n weyland wait --for=condition=failed job/model-watch-neg --timeout=180s; kubectl -n weyland logs job/model-watch-neg --tail=5; kubectl -n weyland delete job model-watch-neg; kubectl -n weyland delete configmap model-watch-neg; rm -r "$T"
```
Expect `FAIL mlflow anthropic-claude-haiku-4-5-md: claude-haiku-4-5 -> claude-haiku-4-5-20251001 retired 2026-10-01;
replacement claude-haiku-5-0` and the container's exit **1**. **RUN 2026-10-21:** exactly that, exit 1.

## UI walkthrough

- **Woodpecker** — `https://woodpecker.weyland.lab/repos/2`: open the latest pipeline, step
  **repo-guards**. **UAT:** the log shows the `model-deprecations: OK — 7 Anthropic model reference(s) …` line, and the
  step is green.
- **Argo CD** — `https://argocd.weyland.lab/applications/argocd/bifrost`. **UAT:** the app tree shows CronJob
  `anthropic-model-watch` and ConfigMap `anthropic-model-watch-logic`, both Synced and Healthy. After step 4, the
  manual Job appears under the CronJob with a completed pod.
- **Grafana alert rules** — `https://grafana.weyland.lab/alerting/list`, search `ScheduledJobFailed`. **UAT:** the
  rule's query names `anthropic-model-watch` in its `job_name` regex, and no `anthropic-model-watch` instance of it is
  firing (the rule as a whole may be Firing for some other job; filter its instances by `job_name`).

## RUN

**2026-10-19, repo side (before the push):**
- **Step 1:** exit 0, `7 Anthropic model reference(s) in 1861 file(s)`, 0 warnings.
- **Step 2:** `FAIL k8s/c.yaml:1 … retired 2026-02-19; replacement claude-haiku-4-5-20251001`, exit 1.
- **Step 3:** covered by the bats suite `scripts/tests/model-deprecations.bats`, 8/8 in the CI `bats/bats` image.
- **Tests:** `test_model_lifecycle.py` 57/57. The CI Python lane passes, and coverage for `scripts/` rose from 69% to 90%.
- **Live logic against the real sources:** MLflow through its NodePort, Bifrost read inside its pod, and Anthropic
  `GET /v1/models`. Result: `OK mlflow anthropic-claude-haiku-4-5-md: claude-haiku-4-5 -> claude-haiku-4-5-20251001
  active`; 14 models offered; exit 0.

**In-cluster, 2026-10-20 (after push `ec8c3856`):**
- **CI #437:** green; its repo-guards log shows `model-deprecations: OK — 7 Anthropic model reference(s) in 1153 file(s)` (a clean checkout; the 1861 above includes untracked files).
- **Argo:** created CronJob `anthropic-model-watch` and its ConfigMap (both files embedded), and the MLflow policy admitted the label.
- **Step 4, Job `anthropic-model-watch-manual-1792468849`:** `succeeded=1 failed=`; `OK mlflow anthropic-claude-haiku-4-5-md: claude-haiku-4-5 -> claude-haiku-4-5-20251001 active (not before 2026-10-15)`; `1 Anthropic model reference(s) … 14 model(s) offered by the API`.
- **A docs fix this run found:** the runbook's first command printed `.status.conditions[0].type`, which is `SuccessCriteriaMet` on this Kubernetes version, not `Complete`. Both docs now print the `succeeded` / `failed` counts.
