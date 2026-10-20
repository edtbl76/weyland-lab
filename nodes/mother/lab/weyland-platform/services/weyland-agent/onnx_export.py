"""Export ONNX models at a pinned commit, then prove the export reproduces recorded output (B216).

WHY THIS EXISTS: the ONNX export stages called `from_pretrained(<repo id>)` with no revision, so a change on the
Hugging Face repo would silently change the exported graph at the next image build. U13 relies on byte-equivalent
embeddings (no vector store re-hydrated after the ONNX switch), so a silently different bge model would quietly
mis-embed every query against vectors built by the old one.

WHAT IT DOES, per service, from that service's `onnx_models.json`:
  build SPEC            export every model AND its tokenizer at `revision` (a 40-hex commit SHA), then run the
                        exported ONNX graph on the spec's fixed `probe` sentence and compare a fingerprint of the
                        output with the recorded `expected` values (within `tolerance`, default 1e-6). A mismatch fails the image
                        build, naming the model.
  build SPEC --record   the same export, but print the actual fingerprints as JSON instead of comparing (to record
                        a NEW pin, after proving it reproduces the deployed model with `probe`). In a Dockerfile:
                        `docker build --build-arg ONNX_EXPORT_RECORD=1` (the export stages declare the ARG).
  probe DIR TASK TEXT   fingerprint an already-exported model directory (model.onnx + tokenizer.json): run inside a
                        deployed image to read what is live.

FINGERPRINTS: feature-extraction -> the CLS vector of the last hidden state (token 0, before the runtime's pooling
and normalisation): its first 8 values and its L2 norm. text-classification -> the logits.

EXIT: 0 every model reproduced · 1 a model's output changed (named) · 2 could not check — a spec that does not pin a
commit or carries no expected values, or an export/probe that failed. Never a silent pass.

ONE SCRIPT, FOUR COPIES: each image builds with its own service directory as the Docker context, so a byte-identical
copy sits in services/{weyland-dagster,weyland-tool-server,weyland-agent,weyland-guard}/; scripts/tests/onnx-export.bats
fails CI when a copy drifts from this file. Stdlib at import time (torch, optimum, onnxruntime and tokenizers are
imported only inside the functions that need them), so the tests run without them.
"""
import json
import math
import os
import re
import sys

TASKS = ("feature-extraction", "text-classification")
HEAD = 8


class SpecError(Exception):
    pass


# ── the spec ─────────────────────────────────────────────────────────────────────────────────────────────────────

def _check_model(m):
    repo = m.get("repo") if isinstance(m, dict) else None
    if not repo:
        raise SpecError(f"a model entry has no `repo`: {m!r}")
    if not re.fullmatch(r"[0-9a-f]{40}", str(m.get("revision", ""))):
        raise SpecError(f"{repo}: `revision` must be a 40-hex commit SHA, got {m.get('revision')!r}")
    if m.get("task") not in TASKS:
        raise SpecError(f"{repo}: `task` must be one of {', '.join(TASKS)}, got {m.get('task')!r}")
    if not str(m.get("out", "")).startswith("/"):
        raise SpecError(f"{repo}: `out` must be an absolute path, got {m.get('out')!r}")
    exp = m.get("expected")
    if not isinstance(exp, dict):
        raise SpecError(f"{repo}: no `expected` fingerprint — record one with `build --record`")
    need = ("cls_head", "cls_norm") if m["task"] == "feature-extraction" else ("logits",)
    missing = [k for k in need if k not in exp]
    if missing:
        raise SpecError(f"{repo}: `expected` needs {', '.join(missing)} for {m['task']}")


def load_spec(path):
    try:
        with open(path, encoding="utf-8") as f:
            spec = json.load(f)
    except (OSError, ValueError) as e:
        raise SpecError(f"cannot read the spec {path}: {e}") from None
    if not isinstance(spec, dict) or not isinstance(spec.get("models"), list) or not spec["models"]:
        raise SpecError(f"{path}: no `models` list")
    if not spec.get("probe"):
        raise SpecError(f"{path}: no `probe` sentence to fingerprint the models with")
    for m in spec["models"]:
        _check_model(m)
    spec.setdefault("tolerance", 1e-6)
    return spec


# ── fingerprints and comparison ──────────────────────────────────────────────────────────────────────────────────

def fingerprint(task, output):
    """The comparable fingerprint of one model's first output (nested lists: batch first)."""
    if task == "feature-extraction":
        cls = [float(x) for x in output[0][0]]
        return {"cls_head": cls[:HEAD], "cls_norm": math.sqrt(sum(x * x for x in cls))}
    return {"logits": [float(x) for x in output[0]]}


def compare(expected, actual, tol):
    """Every field of `expected` that `actual` does not reproduce within `tol`, as readable lines."""
    diffs = []
    for key, exp in expected.items():
        if key not in actual:
            diffs.append(f"{key} missing from the output")
            continue
        act = actual[key]
        if isinstance(exp, list):
            if not isinstance(act, list) or len(act) != len(exp):
                diffs.append(f"{key} has {len(act) if isinstance(act, list) else 'no'} values, expected {len(exp)}")
                continue
            diffs.extend(f"{key}[{i}] expected {e} got {a}" for i, (e, a) in enumerate(zip(exp, act)) if abs(e - a) > tol)
        elif abs(exp - act) > tol:
            diffs.append(f"{key} expected {exp} got {act}")
    return diffs


# ── the heavy parts (export stage / deployed image only) ─────────────────────────────────────────────────────────

def run_export(model):
    """Export the model and its tokenizer at the pinned revision into model['out']."""
    from transformers import AutoTokenizer
    if model["task"] == "feature-extraction":
        from optimum.onnxruntime import ORTModelForFeatureExtraction as Model
    else:
        from optimum.onnxruntime import ORTModelForSequenceClassification as Model
    Model.from_pretrained(model["repo"], revision=model["revision"], export=True).save_pretrained(model["out"])
    AutoTokenizer.from_pretrained(model["repo"], revision=model["revision"]).save_pretrained(model["out"])


def probe_dir(directory, task, text):
    """Fingerprint an exported model directory on `text`, the way the runtime feeds it (no padding/truncation)."""
    import numpy as np
    import onnxruntime as ort
    from tokenizers import Tokenizer
    tok = Tokenizer.from_file(os.path.join(directory, "tokenizer.json"))
    tok.no_padding()
    tok.no_truncation()
    enc = tok.encode(text)
    sess = ort.InferenceSession(os.path.join(directory, "model.onnx"), providers=["CPUExecutionProvider"])
    wanted = {i.name for i in sess.get_inputs()}
    feed = {"input_ids": enc.ids, "attention_mask": enc.attention_mask, "token_type_ids": enc.type_ids}
    out = sess.run(None, {k: np.array([v], dtype=np.int64) for k, v in feed.items() if k in wanted})[0]
    return fingerprint(task, out.tolist())


def run_probe(model, text):
    return probe_dir(model["out"], model["task"], text)


# ── entry point ──────────────────────────────────────────────────────────────────────────────────────────────────

def _build(spec_path, record, export, probe):
    try:
        spec = load_spec(spec_path)
    except SpecError as e:
        print(f"onnx-export: BAD SPEC — {e}")
        return 2
    actual = {}
    for m in spec["models"]:
        tag = f"{m['repo']}@{m['revision'][:8]}"
        try:
            export(m)
            actual[m["repo"]] = probe(m, spec["probe"])
        # Any export or probe failure (network, a missing file, a toolchain error) is "could not check", never a pass.
        except Exception as e:  # noqa: BLE001
            print(f"onnx-export: CANNOT CHECK {tag} — {type(e).__name__}: {e}")
            return 2
    if record:
        print(json.dumps(actual))
        return 0
    failed = 0
    for m in spec["models"]:
        tag = f"{m['repo']}@{m['revision'][:8]}"
        diffs = compare(m["expected"], actual[m["repo"]], spec["tolerance"])
        if diffs:
            failed += 1
            print(f"MISMATCH {tag} -> {m['out']}: " + "; ".join(diffs[:4]))
        else:
            print(f"OK {tag} -> {m['out']} reproduces the recorded output")
    if failed:
        print(f"onnx-export: FAIL — {failed} model(s) no longer reproduce the recorded output. A pinned commit cannot "
              "change, so this is the toolchain (torch/optimum/transformers) exporting differently; see "
              "docs/runbooks/onnx-models.md before re-recording.")
    return 1 if failed else 0


def main(argv=None, export=None, probe=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) >= 2 and argv[0] == "build":
        record = "--record" in argv[2:] or os.environ.get("ONNX_EXPORT_RECORD") == "1"
        return _build(argv[1], record, export or run_export, probe or run_probe)
    if len(argv) == 4 and argv[0] == "probe":
        print(json.dumps(probe_dir(argv[1], argv[2], argv[3])))
        return 0
    print("usage: onnx_export.py build SPEC [--record] | probe DIR TASK TEXT", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
