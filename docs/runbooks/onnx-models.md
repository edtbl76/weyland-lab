# ONNX model exports — pinned commits and the reproduce check (B216)

Four images bake ONNX models in a throwaway export stage, which is the only place torch lives (U13). Each export is
pinned to a Hugging Face **commit**, and the build proves that the export reproduces the output the deployed model gave.

| Image (service dir) | Export stage | Models (pinned commit) | Exported to |
|---|---|---|---|
| weyland-dagster-user-code (`services/weyland-dagster`) | `bge-export` | `BAAI/bge-base-en-v1.5` @ `a5beb1e3`, `BAAI/bge-small-en-v1.5` @ `5c38ec7c` | `/app/bge_onnx_base`, `/app/bge_onnx_small` |
| weyland-tool-server | `bge-export` | `BAAI/bge-base-en-v1.5` @ `a5beb1e3` | `/app/bge_onnx` |
| weyland-agent (hand-tagged) | `bge-export` | `BAAI/bge-base-en-v1.5` @ `a5beb1e3` | `/app/bge_onnx` |
| weyland-guard | `onnx-export` | `cross-encoder/nli-deberta-v3-small` @ `fa280487`, `project-free-llama/Llama-Prompt-Guard-2-22M` @ `98f241c6` | `/app/nli_onnx`, `/app/prompt_guard_onnx` |

**Why the pin matters.** Without it, `from_pretrained(<repo>)` takes whatever the repo holds at build time. U13 swapped
sentence-transformers for raw ONNX *without re-hydrating any vector store*, which is only safe because the embeddings
are byte-equivalent. A silently changed bge model would mis-embed every query against vectors the old one built, with
no error anywhere. The Prompt Guard copy comes from `project-free-llama`, an unofficial ungated mirror of Meta's gated
model, so a pin plus an output check is also the only thing that would notice its weights changing.

## How it works

Each service directory holds `onnx_models.json` (repo, 40-hex `revision`, task, output dir, and the `expected`
fingerprint) and `onnx_export.py`, a byte-identical copy of `scripts/onnx_export.py`. The bats test
`scripts/tests/onnx-export.bats` fails CI on any drift between the copies, and on any Dockerfile that calls
`from_pretrained` outside this path. The export stage runs:

```
RUN python /tmp/onnx/onnx_export.py build /tmp/onnx/onnx_models.json
```

It exports each model and tokenizer at the pinned commit, runs the exported graph on the spec's fixed `probe`
sentence, and compares a **fingerprint** (feature models: the first 8 values and the L2 norm of the CLS vector;
classifiers: the logits) with `expected`, within `tolerance` (1e-6). Output per model is `OK <repo>@<sha8> -> <dir>`.
A mismatch prints `MISMATCH <repo>@<sha8> …` with the differing fields, and **fails the image build**. A spec that does
not pin a commit, or that lacks expected values, exits 2: `BAD SPEC`.

## A build fails with MISMATCH

A pinned commit cannot change, so a mismatch means the **toolchain** exported the same weights differently: torch,
optimum or transformers moved in `requirements-*-export.txt`. Don't re-record the value to make the build pass.
1. Find what changed in the export requirements since the last green build.
2. If the change is deliberate, measure the new export against the old one on real retrieval (the golden set,
   [embedding-model-swap.md](embedding-model-swap.md)). A different embedding space means re-hydrating every vector
   store that model fed, so that runbook's full migration applies.
3. Only then record the new values (below).

## Read what is deployed (the probe)

Fingerprint the model inside a running image, using the same code the build uses:

[rogueone]
```
docker run --rm -v /home/edwardmangini/IdeaProjects/weyland/scripts/onnx_export.py:/x/onnx_export.py:ro --entrypoint python registry.weyland.lab/weyland-agent:v10 /x/onnx_export.py probe /app/bge_onnx feature-extraction "Weyland pins every model it exports."
```

Swap the image, model directory and task (`text-classification` for the guard's `/app/nli_onnx` and
`/app/prompt_guard_onnx`) per the table above. The probe sentence must be the spec's `probe`.

## Change a pin, or record a new value

1. Find the commit you want on the model's Hugging Face page (Files → History), or with
   `https://huggingface.co/api/models/<repo>/commits/main`. Use the full 40-hex SHA.
2. Set `revision` in that service's `onnx_models.json`, and in every other service that exports the same model
   (bge-base is in three).
3. Print the new fingerprints without failing the build. The export stages declare `ARG ONNX_EXPORT_RECORD`, so
   (here for weyland-agent; use `--target onnx-export` for weyland-guard):
   [rogueone]
   ```
   docker build --progress=plain --no-cache --target bge-export --build-arg ONNX_EXPORT_RECORD=1 -t onnx-record /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/services/weyland-agent 2>&1 | grep -E '^#[0-9]+ [0-9.]+ \{'
   ```
   The line is `{repo: fingerprint}` as JSON. Copy each into `expected`, then build normally (no build arg) and
   expect `OK` for every model. CI never sets the arg.
4. Changing the embedding model itself (not just its pin) is the full migration in
   [embedding-model-swap.md](embedding-model-swap.md).

If you edit `scripts/onnx_export.py`, copy it into all four service directories. The bats test names any that differ:

[rogueone]
```
for s in weyland-dagster weyland-tool-server weyland-agent weyland-guard; do cp /home/edwardmangini/IdeaProjects/weyland/scripts/onnx_export.py /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/services/$s/; done
```
