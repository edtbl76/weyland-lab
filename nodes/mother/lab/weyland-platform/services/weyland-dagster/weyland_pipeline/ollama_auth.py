"""The header every Dagster call to Ollama sends (B211, 2026-10-22).

rogueone's Ollama sits behind a front door that answers 401 to a remote caller without the bearer token (the
`ollama-proxy-token` secret, injected as OLLAMA_API_KEY). Read at call time, so a test or a run can set it late.
Dagster-free on purpose: gpu.py and the eval assets all import it.
"""
import os


def ollama_headers() -> dict:
    return {"Authorization": f"Bearer {os.environ.get('OLLAMA_API_KEY', 'ollama')}"}
