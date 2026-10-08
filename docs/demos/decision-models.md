# Demo: decision models, Jev and Clef-flash, as the operator's shadow (B174)

After every incident sweep, the operator asks a decision model which tool it should have opened with, and counts
whether that matches what qwen actually called first. Jev (TypeSafe's hosted API) is the default; Clef-flash
(Cloudflare, Apache-2.0) runs on rogueone on demand, behind the same API. The verdict and the benchmark are in
[concepts/decision-models.md](../concepts/decision-models.md); operating it is in
[runbooks/decision-models.md](../runbooks/decision-models.md). The CLI part was RUN on 2026-10-07 on rogueone.

## Sequence diagram
See [../diagrams/flow-decision-shadow.md](../diagrams/flow-decision-shadow.md).

## Prerequisites
- `TYPESAFE_API_KEY` in `scripts/.env`.
- The native Docker engine with the GPU on rogueone, for Clef-flash.

## CLI walkthrough

**1. The benchmark: three backends on 59 labelled operator decisions.**
```
python3 /home/edwardmangini/IdeaProjects/weyland/eval/decision-model/run.py score
```
```
clef_gpu4    54/59  real-sweep 19/23 real-chat 6/6 written 29/30  median 644 ms  p95 677 ms
jev          53/59  real-sweep 18/23 real-chat 6/6 written 29/30  median 166 ms  p95 204 ms
qwen         54/59  real-sweep 22/23 real-chat 6/6 written 26/30  median 687 ms  p95 2445 ms
```
Jev's run used 119,076 input tokens, about $0.005.

**2. The shadow against the real Jev API, from inside the operator image.** It agrees with the baseline and counts
the tokens. Load the key first (`set -a && . /home/edwardmangini/IdeaProjects/weyland/scripts/.env && set +a`), then
run:
```
docker run --rm -e TYPESAFE_API_KEY -e OPERATOR_DECIDE_SHADOW=true weyland-operator:b174-local python -c "
import asyncio, httpx, decide
async def main():
    async with httpx.AsyncClient() as client:
        print(await decide.shadow(client, 'You are the weyland homelab operator.', 'Alert: NodeMemoryHighUtilization (severity warning) on 192.168.1.243:9100.', [('k8s_nodes_top', 'List the CPU and memory use of nodes'), ('k8s_pods_list', 'List all pods'), ('status', 'Lab health')], actual='k8s_nodes_top', alert='NodeMemoryHighUtilization'))
asyncio.run(main())"
```
```
[decide] alert=NodeMemoryHighUtilization backend=jev pick=k8s_nodes_top confidence=0.56 operator=k8s_nodes_top outcome=agree
{'choice': 'k8s_nodes_top', 'confidence': 0.56, 'outcome': 'agree', 'seconds': 0.177}
```

**3. Negative: a bad key is counted as an error and never raises.** Run the same command with `-e TYPESAFE_API_KEY=wrong`
in place of `-e TYPESAFE_API_KEY`. It still exits 0, so the sweep would carry on:
```
[decide] jev shadow failed for NodeMemoryHighUtilization: Client error '401 Unauthorized' for url 'https://api.typesafe.ai/v1/systemone'
None
```

**4. Clef-flash on demand.** The run starts the server, checks it, routes the shadow to it, then stops it:
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/clef-flash.sh start
bash /home/edwardmangini/IdeaProjects/weyland/scripts/clef-flash.sh smoke
bash /home/edwardmangini/IdeaProjects/weyland/scripts/clef-flash.sh stop
```
- **Start and health:** healthy after about 180 s; the card was at 12.9 GB with the desktop.
- **Smoke:** `team -> technical (confidence 0.9429)`.
- **The shadow pointed at Clef:** `OPERATOR_DECIDE_URL=http://localhost:8004/v1/systemone`,
  `OPERATOR_DECIDE_MODEL=clef-flash`. It returned `pick=k8s_nodes_top confidence=0.94 outcome=agree` in 0.13 s, and
  `auth header sent over http: False`.
- **Stop:** `Clef-flash stopped; qwen2.5:7b-operator back fully on the GPU (6593561230 bytes)`.
- **Live operator during the window:** `operator_brain_selected_total` showed no `local_error`.

**5. Negative: the wrapper fails closed.** The bats suite (`scripts/tests/clef-flash.bats`, 9 cases) covers four
failure cases:
- smoke with no server is exit 1;
- smoke on an error body or an empty reply is exit 1, `SMOKE FAILED`;
- `stop` exits 1 when qwen came back partly on the CPU (`vram=878150942 of 6825818035`, the real 2026-10-07 numbers)
  or did not load;
- no verb prints usage and exits 2.

Planting "smoke always passes" or "skip the GPU check" in a copy of the script fails tests 4, 5 and 7.

**6. The alerts.** `scripts/tests/alert-rules.bats` runs promtool on `OperatorDecideShadowFailing` and
`OperatorDecideSpendObserved`:
- only errors for 2h fires;
- errors mixed with successes, and no calls at all, are both silent;
- about $1.26 of spend in a day fires, and a busy normal day (100 sweeps) is silent.

## UI walkthrough (UAT, eyes on)

This runs after the key is sealed and the operator image is shipped.
1. **Grafana Explore (Prometheus):** `sum by (backend, outcome, confident) (increase(operator_decide_shadow_total[24h]))`.
   After the next sweep, a `backend="jev"` row shows `agree`, `disagree` or `no_baseline`, and no `error`.
2. **Grafana Alerting:** `OperatorDecideShadowFailing` and `OperatorDecideSpendObserved` are listed and inactive.
3. **Telegram:** the incident digest looks exactly as before. The shadow's pick never appears in it.

**UAT result (2026-10-07):** the owner saw both alert rules and ran the Explore query. Shipped as
`weyland-operator:git-ab941110` (CI #286, PR #140). First live shadow pick:
`[decide] alert=KubePodOOMKilled backend=jev pick=k8s_events_list confidence=0.42 operator=k8s_pods_list outcome=disagree`.
Both picks are valid first moves for that alert under the benchmark's labels. The same evening it showed that
`increase()` hides a series' first increment (the row read 0), so the cookbook and runbook now give the running-total
query for early days. The **App Services** dashboard gained a row for the operator's brain, sweep and shadow
metrics.

## Expected result
- Each enriched sweep adds one `operator_decide_shadow_total` sample, with about 2K Jev input tokens.
- The sweep's behavior and digest are unchanged.
- A bad key, no credit or an outage is counted as an error and alerts after 2h. It never breaks the sweep.

## Cleanup / teardown
- **Clef-flash:** `scripts/clef-flash.sh stop` frees the card and reloads qwen. The weights stay in the `hf-cache`
  volume, about 19 GB. To remove them:
  `docker -H unix:///var/run/docker.sock run --rm -v gpu-inference_hf-cache:/c alpine rm -rf /c/hub/models--Cloudflare--clef-flash`.
- **Jev:** stateless; nothing to clean up.
- **The local test image:** `docker rmi weyland-operator:b174-local`.
