"""Reusable GPU/Ollama helpers.

`drain_gpu` unloads all resident Ollama models and waits until the shared 16 GB card
is clear before the next load. On a single-model-at-a-time GPU (rogueone runs
`OLLAMA_MAX_LOADED_MODELS=1`), requesting a new model while another is resident makes
Ollama evict-and-reload mid-request, which returns 503 for the load window — the
source of the eval matrix's swap thrash. Draining first means each model loads into a
clean card (still a load pause, which the caller's retry rides out) instead of racing
an eviction. Capability, not snowflake: any asset that switches Ollama models can use it.
"""
import time

import httpx


def _api_base(ollama_url: str) -> str:
    # The eval / tool-server use the OpenAI-compat ".../v1" base; the native unload
    # (/api/generate keep_alive:0) and /api/ps live off the root.
    return ollama_url.rstrip("/").removesuffix("/v1")


def _resident(base: str) -> list[str]:
    try:
        r = httpx.get(f"{base}/api/ps", timeout=10)
        r.raise_for_status()
        return [m.get("model") or m.get("name") for m in r.json().get("models", [])]
    except Exception:
        return []


def drain_gpu(ollama_url: str, timeout_s: int = 90, poll_s: float = 2.0, log=None) -> dict:
    """Unload every resident Ollama model and poll until /api/ps is empty.

    Returns {"clear": bool, "waited_s": float, "held": [str]}. Never raises on a normal
    timeout — a model that won't release usually means the GPU is wedged (rogueone's
    known instability); the caller decides whether that's fatal.
    """
    base = _api_base(ollama_url)

    def _say(m):
        if log is not None:
            log.info(m)

    resident = _resident(base)
    if not resident:
        return {"clear": True, "waited_s": 0.0, "held": []}
    _say(f"[drain] unloading resident model(s): {resident}")
    for m in resident:
        try:
            httpx.post(f"{base}/api/generate", json={"model": m, "keep_alive": 0, "prompt": ""}, timeout=30)
        except Exception as e:
            _say(f"[drain] unload request for {m} errored (continuing to poll): {e}")

    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout_s:
        held = _resident(base)
        if not held:
            waited = time.monotonic() - t0
            _say(f"[drain] GPU clear in {waited:.1f}s")
            return {"clear": True, "waited_s": waited, "held": []}
        time.sleep(poll_s)

    held = _resident(base)
    _say(f"[drain] TIMEOUT after {timeout_s}s — still resident: {held} (GPU may be wedged)")
    return {"clear": False, "waited_s": float(timeout_s), "held": held}
