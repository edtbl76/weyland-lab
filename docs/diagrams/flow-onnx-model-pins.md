# Flow — pinned ONNX exports (B216)

Every image that bakes an ONNX model exports it at a pinned Hugging Face commit and proves, inside its own build, that
the export reproduces the output recorded from the deployed model. Operate: [runbooks/onnx-models.md](../runbooks/onnx-models.md).

```mermaid
sequenceDiagram
    participant B as image build (export stage)
    participant X as onnx_export.py build
    participant S as onnx_models.json
    participant H as Hugging Face repo at a commit
    participant R as onnxruntime on the export
    B->>X: RUN onnx_export.py build onnx_models.json
    X->>S: load and validate the spec
    alt a revision is not a 40-hex commit, or no expected values
        X-->>B: exit 2, BAD SPEC, the build fails
    else spec valid
        loop each model
            X->>H: from_pretrained at the pinned revision, model and tokenizer
            H-->>X: weights and tokenizer, unchanged since the pin
            X->>R: run the exported graph on the fixed probe sentence
            R-->>X: fingerprint, CLS head and norm, or logits
        end
        alt an export or probe failed
            X-->>B: exit 2, CANNOT CHECK, the build fails
        else every fingerprint within tolerance of expected
            X-->>B: exit 0, OK per model, the image builds
        else a fingerprint differs
            X-->>B: exit 1, MISMATCH naming the model, the build fails
        end
    end
```
