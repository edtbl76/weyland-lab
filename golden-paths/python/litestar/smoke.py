"""Ephemeral smoke — proves the BUILT image serves the deep contract v2, run-to-completion (B153; B261).

The `golden-python-litestar` k8s Job runs `python smoke.py`: it starts the real uvicorn server the image ships (the
`main:serve` factory) and runs the shared v2 sequence (v2_smoke.py, a synced copy of golden-paths-shared/python).
"""
import sys

from v2_smoke import PORT, run

if __name__ == "__main__":
    sys.exit(run(["uvicorn", "--factory", "main:serve", "--host", "127.0.0.1", "--port", str(PORT)]))
