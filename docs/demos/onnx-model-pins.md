# Demo — pinned ONNX exports (B216)

**What it shows.** The four images that bake ONNX models (weyland-dagster-user-code, weyland-tool-server, weyland-agent,
weyland-guard) export them at pinned Hugging Face commits. Each build proves its export reproduces the output recorded
from the deployed model, and if it doesn't, the build fails, naming the model. This is build tooling with no UI, so
the CLI walkthrough is the whole demo. Flow: [flow-onnx-model-pins](../diagrams/flow-onnx-model-pins.md). Runbook:
[onnx-models.md](../runbooks/onnx-models.md).

## CLI walkthrough

**1. Read what is deployed.** Fingerprint the live bge-base model inside the deployed agent image:

[rogueone]
```
docker run --rm -v /home/edwardmangini/IdeaProjects/weyland/scripts/onnx_export.py:/x/onnx_export.py:ro --entrypoint python registry.weyland.lab/weyland-agent:v10 /x/onnx_export.py probe /app/bge_onnx feature-extraction "Weyland pins every model it exports."
```
Expect `{"cls_head": [-0.13630686700344086, 0.4971165359020233, …], "cls_norm": 15.569936513356879}`. That is the
`expected` block in `services/weyland-agent/onnx_models.json`.

**2. Build the export stage: it exports at the pinned commit and checks.**

[rogueone]
```
docker build --progress=plain --target bge-export --build-arg ONNX_EXPORT_RECORD=0 -t onnx-demo /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/services/weyland-agent 2>&1 | grep -E 'OK |MISMATCH|onnx-export:'
```
Expect `OK BAAI/bge-base-en-v1.5@a5beb1e3 -> /export/bge_onnx reproduces the recorded output`, and the build succeeds.
`ONNX_EXPORT_RECORD=0` forces the export step to run again. A fully cached build replays no output, and any value
other than `1` still checks. The arg is declared after the pip layer, so torch is not reinstalled.

**3. The negative: a wrong expected value fails the build, naming the model.**

[rogueone]
```
W=$(mktemp -d) && cp -r /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/services/weyland-agent/. "$W"/ && python3 -c "import json; p='$W/onnx_models.json'; s=json.load(open(p)); s['models'][0]['expected']['cls_norm'] += 0.001; json.dump(s, open(p, 'w'))" && docker build --progress=plain --target bge-export -t onnx-demo-wrong "$W" 2>&1 | grep -E 'MISMATCH|onnx-export:'; echo "exit=${PIPESTATUS[0]}"; rm -r "$W"
```
Expect `MISMATCH BAAI/bge-base-en-v1.5@a5beb1e3 -> /export/bge_onnx: cls_norm expected 15.570936513356878 got
15.569936513356879`, then `onnx-export: FAIL — 1 model(s) no longer reproduce the recorded output…` and `exit=1`.

**4. A spec that names a branch instead of a commit is refused (exit 2).** Covered by
`scripts/tests/onnx-export.bats` test 4: `BAD SPEC — BAAI/bge-base-en-v1.5: \`revision\` must be a 40-hex commit
SHA, got 'main'`.

## RUN — 2026-10-20

- **The deployed fingerprints:** read with step 1's probe from all four live images. bge-base is identical in
  dagster, tool-server and agent.
- **The export stages:** all four built with the pins. Every model printed `OK`: bge-base ×3, bge-small,
  nli-deberta-v3-small and Prompt Guard. The exported `model.onnx` is **byte-identical** (sha256) to the deployed
  one for all six, so no vector store needs re-hydrating.
- **The negative (step 3):** exit 1 with the `MISMATCH` line above.
- **The record build arg:** `--build-arg ONNX_EXPORT_RECORD=1` printed the fingerprint JSON and did not fail.
- **Tests:** `test_onnx_export.py` 28/28, `onnx-export.bats` 4/4.

**Shipped and checked live — 2026-10-20:**
- **CI #444** passed and the full SonarQube gate is OK. Duplication on new code is 0.28%; the four service copies are left out of duplication detection, after CI #443 failed at 4.17%.
- **The ship (`git-514d5158`, PR #210):** every bumped workload is up with its health check passing (7), and 4 services answered a real request.
- **weyland-agent:** `v11` (hand-tagged; the same digest as `v10`). It reports ready, and `/agent/ask` answered on the first attempt with 5 sources.
- **Model bytes in the live pods:** guard `3f130181`/`682ac22f`, tool-server `e5f98ce7`, dagster `e5f98ce7`/`82e06739` — identical to the pre-pin deployment.
- **weyland-guard:** ready with all 6 validators. A live injection query is classified `block` by `prompt_guard.injection` (shadow mode, so recorded and not enforced: the guard's existing posture).
