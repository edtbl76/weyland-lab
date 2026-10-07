"""Clef-flash on demand (B174) — Cloudflare's Apache-2.0 decision model behind the Jev / SystemOne API.

`POST /v1/systemone` takes a Jev request body ({"model", "state", "questions"}) and returns Jev's response body
({"model", "answers", "usage"}), so a caller switches between TypeSafe's hosted Jev and this server by URL alone — the
weyland-operator's decision-model shadow (services/weyland-operator/decide.py) does exactly that. `GET /health` is 200
once the model is loaded. One request at a time: it is one model on one GPU.

Loaded 4-bit NF4 (~8.5 GB peak of the 16 GB card): it does NOT fit beside the operator's qwen2.5:7b-operator, so it runs
on demand only — scripts/clef-flash.sh start|stop, never always-on. The decision head is the model repo's own Python
(joint_schema_model.py), which is why the revision is pinned to a full commit. Runbook: docs/runbooks/decision-models.md.
"""
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPO = "Cloudflare/clef-flash"
REVISION = os.environ.get("CLEF_REVISION", "17f0b0ad64efb65d273590632833508766b2aae6")   # benchmarked 2026-10-07
PORT = int(os.environ.get("PORT", "8080"))
MAX_BODY = 1_000_000          # a decision request is a state + a few questions; 1 MB is generous
MAX_LENGTH = 16384            # the model card's encode_record default — longer states are cut by the model code


class BadRequest(ValueError):
    pass


def parse(raw: bytes) -> dict:
    """The request contract: a JSON object with a `state` and a non-empty `questions` mapping."""
    try:
        request = json.loads(raw)
    except ValueError as exc:
        raise BadRequest(f"body is not JSON: {exc}") from exc
    if not isinstance(request, dict):
        raise BadRequest("body must be a JSON object")
    if "state" not in request:
        raise BadRequest("missing `state`")
    if not isinstance(request.get("questions"), dict) or not request["questions"]:
        raise BadRequest("`questions` must be a non-empty object of question id -> question")
    return request


def handle(raw: bytes, decide) -> tuple[int, dict]:
    """One request through `decide` (the model). Every failure is an error status with its reason — never an answer."""
    if len(raw) > MAX_BODY:
        return 413, {"error": f"body over {MAX_BODY} bytes"}
    try:
        request = parse(raw)
    except BadRequest as exc:
        return 400, {"error": str(exc)}
    try:
        return 200, decide(request)
    except Exception as exc:   # the caller gets the reason; the server stays up for the next request
        return 500, {"error": f"{type(exc).__name__}: {exc}"}


def load():
    """Download (cached in the hf-cache volume) and load the pinned model 4-bit on the GPU; return request -> answer."""
    import torch
    from huggingface_hub import snapshot_download
    from transformers import BitsAndBytesConfig

    path = snapshot_download(REPO, revision=REVISION)
    sys.path.insert(0, path)
    from joint_schema_model import load_release_model, systemone

    quantization = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                      bnb_4bit_compute_dtype=torch.bfloat16)
    model, processor = load_release_model(path, device="cuda", quantization_config=quantization)
    lock = threading.Lock()

    def decide(request: dict) -> dict:
        with lock:
            return systemone(model, processor, request, max_length=MAX_LENGTH)
    return decide


def serve(decide) -> None:
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, body: dict) -> None:
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):   # noqa: N802 — http.server's naming
            if self.path == "/health":
                self._send(200, {"status": "ok", "model": REPO, "revision": REVISION})
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):   # noqa: N802
            if self.path != "/v1/systemone":
                self._send(404, {"error": "not found"})
                return
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(min(length, MAX_BODY + 1))
            self._send(*handle(raw, decide))

    print(f"clef-flash {REVISION[:12]} serving :{PORT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()   # nosec B104 — LAN service in a container


if __name__ == "__main__":
    serve(load())
