# Demo — weyland consumes grkit's verdict contract (B206 slice 2)

weyland-guard decides PASS/FLAG/BLOCK; weyland-tool-server calls it over HTTP. The words they share (`Hook` values are
the URL paths, `Decision` values are parsed from the response, `Verdict` is built positionally) used to live in two
byte-identical copies of `guardrails/verdict.py`, held together by `scripts/check-verdict-sync.sh`. Since 2026-10-15
both import one module, `grkit.verdict`, from [grkit](https://github.com/edtbl76/grkit) (public, MIT), the guardrails kit
packaged from this lab. This demo proves both live services run the same pinned grkit, that the pin can't drift
unnoticed, and that the guard still enforces through the shared contract.

Runbook: [../runbooks/guardrails.md](../runbooks/guardrails.md) § The wire contract comes from grkit (how to bump the
pin). The request path itself is unchanged: [../diagrams/flow-act-tool.md](../diagrams/flow-act-tool.md).

## CLI walkthrough (run 2026-10-15 against the live cluster, images `git-a68d3d90`)

`kubectl` works from rogueone or mother. Every step only reads.

**1. Both services run grkit from the same pinned commit:**

```
for d in weyland-guard weyland-tool-server; do kubectl -n weyland exec deploy/$d -c $d -- python -c "import importlib.metadata as m, grkit.verdict as v, json; d=m.distribution('grkit'); print('$d', 'grkit', d.version, json.loads(d.read_text('direct_url.json') or '{}').get('url','?')[-80:], 'Verdict from', v.Verdict.__module__)"; done
```
Observed:
```
weyland-guard grkit 0.2.0 github.com/edtbl76/grkit/archive/0d0797785c3e802d801cc1185dad7a41f473d72e.tar.gz Verdict from grkit.verdict
weyland-tool-server grkit 0.2.0 github.com/edtbl76/grkit/archive/0d0797785c3e802d801cc1185dad7a41f473d72e.tar.gz Verdict from grkit.verdict
```

**2. Neither carries its own copy any more:**

```
kubectl -n weyland exec deploy/weyland-tool-server -c weyland-tool-server -- sh -c 'test -e /app/guardrails && echo "guardrails present" || echo "no guardrails dir"'
```
Observed: `no guardrails dir`. (weyland-guard's `guardrails/` keeps its policy and validators, minus `verdict.py`.)

**3. The pin can't drift between the two services.** Two copies can no longer diverge, but two pins can, so one bats
test holds every grkit reference (both Dockerfiles, both test requirement files) to one commit-pinned URL:

```
docker run --rm -v /home/edwardmangini/IdeaProjects/weyland:/w:ro -w /w bats/bats:latest scripts/tests/grkit-pin.bats
```
Observed: `ok 1 every grkit pin in the repo is the same commit-pinned archive URL` · `ok 2 both services pin grkit in their
image AND their test lane` · `ok 3 a pin that drifts in one file is caught (the check is not a rubber stamp)` · `ok 4 no
service carries its own guardrails/verdict.py again`. Test 3 is the negative case: two different commits in two files
are reported as two URLs.

**4. The guard still enforces through the shared contract.** The tool-server builds its verdict from the guard's JSON with
grkit's types, so a refusal proves the round trip ([act-guard.md](act-guard.md) step 3, same command):

```
kubectl -n weyland exec deploy/weyland-tool-server -c weyland-tool-server -- python -c $'import urllib.request as u, urllib.error as e, json\ndef call(m, p, h=None, b=None):\n    r = u.Request("http://localhost:8080" + p, data=b, method=m, headers=h or {})\n    try:\n        x = u.urlopen(r, timeout=30); print(p, x.status, x.read()[:300].decode())\n    except e.HTTPError as x:\n        print(p, x.code, x.read()[:300].decode())\ncall("POST", "/pipeline/trigger", {"Content-Type": "application/json", "X-Forwarded-Consumer": "b207-drill-not-allowlisted"}, json.dumps({"job_name": "weyland_ingestion_job"}).encode())\n'
```
Observed: `/pipeline/trigger 403 {"detail":"blocked by policy.gate: actor 'b207-drill-not-allowlisted' not in the act
allowlist"}`. And a benign question passes:

```
kubectl -n weyland exec deploy/weyland-tool-server -c weyland-tool-server -- python -c "import json,urllib.request as u; r=u.Request('http://weyland-guard.weyland.svc.cluster.local:8080/guard/input',data=json.dumps({'request_id':'b206-check','query':'How many namespaces are in the cluster?'}).encode(),headers={'Content-Type':'application/json'}); print(u.urlopen(r,timeout=30).read().decode())"
```
Observed: `{"request_id":"b206-check","decision":"allow","verdict":null}`.

**5. The contract test** (`weyland-guard/tests/test_verdict_contract.py`, in CI's python lane) pins grkit's Hook,
Decision and Mode values, Verdict's positional field order and the guard response round-trip, so a grkit release that
changed any of them fails at the pin bump, not in production.

## UI walkthrough

No UI is a deliverable here: grkit is a library inside two images. Its home is the GitHub repo,
https://github.com/edtbl76/grkit (README: the principle, both adoption paths), and its catalog entry is the Port
component `grkit` (group `library`). UAT: open the repo and confirm the tag `v0.2.0` points at commit `0d07977`, the
commit both services pin.

## Cleanup / teardown

Read-only: step 4's refused act launches nothing, and the benign check writes one `pass` row to `guardrail_verdicts`
(the guard records every verdict; kept on purpose, like the act-guard demo's rows).
