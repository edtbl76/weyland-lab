"""OpenAI-compatible /v1/audio/transcriptions shim for whisper.cpp.

whisper.cpp's `whisper-server` only exposes `/inference`; OpenAI clients (OpenClaw,
the tool server, anything speaking the OpenAI audio API) expect
`POST /v1/audio/transcriptions`. This thin adapter translates between them.

Why it returns a STRICT OpenAI shape: OpenClaw's `baseUrl` override for OpenAI-compatible
STT providers falls back *silently* if the response drifts from OpenAI's schema
(openclaw/openclaw#9494). So we ask whisper.cpp for plain text and build the
`{"text": ...}` / raw-text response ourselves — no stray whisper fields leak through.

Runs alongside whisper-server inside CT 103; forwards audio to it on localhost:8080.
Engine-agnostic to its callers: same endpoint shape as OpenAI / Ollama's `/v1`.
"""
import os

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse

# whisper.cpp server's native endpoint (internal to the container).
WHISPER_INFERENCE_URL = os.getenv("WHISPER_INFERENCE_URL", "http://127.0.0.1:8080/inference")
# CPU transcription of a long clip can take a while — keep the timeout generous.
REQUEST_TIMEOUT = float(os.getenv("WHISPER_TIMEOUT", "300"))

app = FastAPI(title="whisper-openai-shim")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/v1/audio/transcriptions")
async def transcriptions(
    file: UploadFile = File(...),
    # Accepted for OpenAI-API compatibility; whisper.cpp serves one loaded model,
    # so `model` is echoed/ignored rather than used to select.
    model: str = Form("whisper-1"),
    response_format: str = Form("json"),
    language: str | None = Form(None),
    temperature: float = Form(0.0),
    prompt: str | None = Form(None),
):
    # Request PLAIN TEXT from whisper.cpp so we own the response shape entirely
    # (strict OpenAI compliance — the #9494 mitigation).
    data = {"response_format": "text", "temperature": str(temperature)}
    if language:
        data["language"] = language
    if prompt:
        data["prompt"] = prompt
    upload = {
        "file": (
            file.filename or "audio",
            await file.read(),
            file.content_type or "application/octet-stream",
        )
    }
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.post(WHISPER_INFERENCE_URL, data=data, files=upload)
            resp.raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"whisper inference failed: {e}")

    text = resp.text.strip()

    # OpenAI semantics: `text` -> raw body; `json`/`verbose_json` (and anything else,
    # incl. srt/vtt which we don't special-case yet) -> minimal {"text": ...}.
    if response_format == "text":
        return PlainTextResponse(text)
    return JSONResponse({"text": text})
