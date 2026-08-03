"""nemo-guardrails — the Dialog layer of the guardrails platform (B115).

NeMo Guardrails (Colang topical + input rails) as a standalone **OpenAI-compatible** service, isolated in its own image
(NeMo's dep tree — langchain etc.). Open WebUI adds it as an OpenAI connection → a guarded **"Weyland Lab Operator"**
chat model appears alongside the raw Ollama models; picking it runs every turn through the input self-check + topical
rails (an off-lab-topic request gets a conversational refusal — NeMo's distinctive DIALOG control, which the edge I/O
scan does NOT do). The raw Ollama models stay unguarded, so general chat is unaffected.

We wrap the NeMo **library** (`LLMRails.generate`, proven in the B32 trial) behind our own `/v1/chat/completions` rather
than NeMo's native server, because that server wants `config_id` nested under a `guardrails` object a vanilla OpenAI
client (Open WebUI) won't send. This gives Open WebUI a plain OpenAI surface; the rails apply transparently. The endpoint
is sync (`def`) so it runs in the threadpool — NeMo's `generate` spins its own event loop, which an `async def` would break.
"""
import json
import os
import time

from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

MODEL_NAME = os.environ.get("NEMO_MODEL_NAME", "weyland-operator")
CONFIG_PATH = os.environ.get("NEMO_CONFIG_PATH", "/app/config")

app = FastAPI(title="nemo-guardrails")

_rails = None  # NeMo + langchain import is heavy — build the rails once, reuse across requests


def _get_rails():
    global _rails
    if _rails is None:
        from nemoguardrails import LLMRails, RailsConfig
        _rails = LLMRails(RailsConfig.from_path(CONFIG_PATH))
    return _rails


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: str | None = None
    stream: bool = False
    # other OpenAI params (temperature, etc.) are ignored — NeMo drives the main model per its own config.


@app.post("/v1/chat/completions")
def chat_completions(req: ChatRequest):
    rails = _get_rails()
    result = rails.generate(messages=[{"role": m.role, "content": m.content} for m in req.messages])
    content = result["content"] if isinstance(result, dict) else str(result)
    model = req.model or MODEL_NAME
    created = int(time.time())

    if req.stream:
        # Open WebUI streams by default; NeMo's generate is non-streaming, so emit the full answer as one SSE chunk.
        def gen():
            first = {"id": "nemo-guardrails", "object": "chat.completion.chunk", "created": created, "model": model,
                     "choices": [{"index": 0, "delta": {"role": "assistant", "content": content}, "finish_reason": None}]}
            yield f"data: {json.dumps(first)}\n\n"
            last = {"id": "nemo-guardrails", "object": "chat.completion.chunk", "created": created, "model": model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
            yield f"data: {json.dumps(last)}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(gen(), media_type="text/event-stream")

    return {"id": "nemo-guardrails", "object": "chat.completion", "created": created, "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}]}


@app.get("/v1/models")
def models():
    """Open WebUI reads this to list the guarded model."""
    return {"object": "list", "data": [{"id": MODEL_NAME, "object": "model", "owned_by": "weyland"}]}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    """Readiness — the rails (NeMo + langchain + the config) actually load. 503 until they do."""
    try:
        _get_rails()
        return {"status": "ready"}
    except Exception as exc:
        return JSONResponse(status_code=503, content={"status": "loading", "error": str(exc)})
