# Decision models: the operator's Jev / Clef-flash shadow (B174)

After every incident sweep, the operator asks a **decision model** which tool it should have opened with, and counts
whether that matches the tool qwen actually called first. It is a **shadow**: nothing acts on the answer, it never
reaches the Telegram digest, and if it fails the sweep is unaffected. It exists to collect evidence on real alerts.
The verdict so far and the benchmark: [concepts/decision-models.md](../concepts/decision-models.md).

| Piece | Where |
|---|---|
| Shadow client | `services/weyland-operator/decide.py`, called from `incidents.py` after the agent run |
| Backend: Jev (default) | TypeSafe's hosted API `https://api.typesafe.ai/v1/systemone`, model `jev-1.13.0`. **Paid** from the owner's prepaid TypeSafe credit: about 2K input tokens a sweep, about $0.0001 |
| Backend: Clef-flash (on demand) | `nodes/rogueone/services/gpu-inference/clef-flash/` (server), `scripts/clef-flash.sh` (wrapper), `:8004` on rogueone. Same API |
| Switches | `k8s/weyland-operator/deployment.yaml`: `OPERATOR_DECIDE_SHADOW`, `OPERATOR_DECIDE_URL`, `OPERATOR_DECIDE_MODEL` |
| Key | Secret `weyland/typesafe-api` (`TYPESAFE_API_KEY`), sealed (`seal-secrets.sh` allow-list); sent **only over https** |
| Metrics | `operator_decide_shadow_total{backend,outcome,confident}` (`outcome` = `agree` · `disagree` · `no_baseline` · `error`) · `operator_decide_input_tokens_total{backend}` · `operator_decide_seconds{backend}` |
| Alerts | `OperatorDecideShadowFailing` (only errors for 2h) · `OperatorDecideSpendObserved` (more than $1 of Jev in 24h), in `k8s/weyland-operator/prometheusrule.yaml` |
| Tests | `services/weyland-operator/tests/test_decide.py` + `test_incidents.py` · `clef-flash/tests/test_server.py` · `scripts/tests/clef-flash.bats` · `scripts/tests/fixtures/alert-rules/operator-decide.test.yaml` |

## First-time setup: the TypeSafe key

The key is already in `scripts/.env` as `TYPESAFE_API_KEY`. Each step below runs on rogueone.

**1. Create the Secret** from that key, without printing it:

[rogueone]
```
set -a && . /home/edwardmangini/IdeaProjects/weyland/scripts/.env && set +a && kubectl -n weyland create secret generic typesafe-api --from-literal=TYPESAFE_API_KEY="$TYPESAFE_API_KEY" --dry-run=client -o yaml | kubectl -n weyland apply -f -
```

**2. Check the STORED value**, not just that the Secret exists. The output must be `107`, the key's length in
`scripts/.env`:

```
kubectl -n weyland get secret typesafe-api -o jsonpath='{.data.TYPESAFE_API_KEY}' | base64 -d | wc -c
```

**3. Seal it into the repo** ([secrets.md](secrets.md) § Rotate / re-seal):

[rogueone]
```
kubectl -n weyland annotate secret typesafe-api sealedsecrets.bitnami.com/managed=true --overwrite && kubectl -n weyland get secret typesafe-api -o yaml | kubeseal --format yaml > /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/k8s/sealed-secrets/sealed/weyland__typesafe-api.yaml
```

**4. Ship it.** Commit and push, then ship the operator image with `scripts/ship-images.sh` ([woodpecker.md](woodpecker.md)).

## Read the evidence

In Grafana Explore (Prometheus):
```
sum by (backend, outcome, confident) (increase(operator_decide_shadow_total[7d]))
```

- **Agreement rate:** `agree / (agree + disagree)`. Read the `confident="true"` rows on their own as well. The question
  is whether confident picks are right often enough to route on (the B174 benchmark: 38 of 38 at confidence 0.5 or
  higher).
- **`no_baseline`:** qwen called no tool, so there was nothing to compare against.
- **Per alert:** each call also logs a line, `[decide] alert=<name> backend=<jev|clef> pick=<tool> confidence=<c>
  operator=<tool> outcome=<…>`. Read them with:

```
kubectl -n weyland logs deploy/weyland-operator | grep '\[decide\]'
```

- **Spend:** `sum(increase(operator_decide_input_tokens_total{backend="jev"}[30d])) * 0.042 / 1e6` in dollars.

## Compare Clef-flash instead (on demand)

Clef-flash holds about 8.5 GB of the 16 GB card, so it can't run beside the operator's qwen. `start` unloads qwen;
while Clef runs, Ollama reloads qwen partly on the CPU, and live operator calls can hit their 60 s timeout. Keep the
window short.

**1. Start Clef-flash.** The first start downloads about 19 GB to the `hf-cache` volume:

[rogueone]
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/clef-flash.sh start
```

**2. Check it.** `status` must print `/health ok`, and `smoke` must print `team -> technical`:

[rogueone]
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/clef-flash.sh status && bash /home/edwardmangini/IdeaProjects/weyland/scripts/clef-flash.sh smoke
```

**3. Point the operator at it.** In `k8s/weyland-operator/deployment.yaml`, set `OPERATOR_DECIDE_URL` to
`http://192.168.1.230:8004/v1/systemone` and `OPERATOR_DECIDE_MODEL` to `clef-flash`. Commit and push; Argo rolls the
pod, and an env change needs no image build. The key is not sent over http. The metrics' `backend` label becomes
`clef`.

**4. Stop it.** `stop` stops the server, reloads qwen, and exits 1 unless qwen is back **fully** on the GPU:

[rogueone]
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/clef-flash.sh stop
```

**5. Point the operator back at Jev** by reverting step 3. If you forget, `OperatorDecideShadowFailing` fires after
2 hours of errors.

## Turn it off

In `k8s/weyland-operator/deployment.yaml`, set `OPERATOR_DECIDE_SHADOW` to `"false"`, then commit and push. The sweep
is unchanged either way.

## Troubleshooting

| Symptom | Cause | Check / fix |
|---|---|---|
| `OperatorDecideShadowFailing` | The key is missing or wrong (401), the credit ran out (402), or TypeSafe is down | The `[decide] ... shadow failed` log line names the HTTP status. Top up the credit or re-seal the key; turn the shadow off meanwhile |
| Every outcome is `no_baseline` | qwen is answering without calling a tool | The sweep itself: [operator.md](operator.md) § Diagnosing a slow / stalled local brain |
| `clef-flash.sh stop` exits 1 | Something else still holds the card, so Ollama put qwen partly on the CPU | `nvidia-smi`, free the card, re-run `stop` |
| Clef-flash build fails on `pip` | The base image's Python is externally managed, or the pins conflict | `requirements.txt` pins what pip resolved in the base image; re-resolve there, never "latest" |

## DR

Nothing to restore. The shadow keeps no state: its evidence is Prometheus counters, and the Clef weights download
again from the pinned commit. The key is a sealed Secret, so it is covered by the sealed-secrets restore
([dr.md](../dr.md)).
