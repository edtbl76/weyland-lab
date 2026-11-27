"""Ephemeral smoke — proves the BUILT image serves the deep contract v2, run-to-completion (B153; B260/B261).

The `golden-python-django` k8s Job runs `python smoke.py`: it starts the real gunicorn server the image ships and runs
the shared v2 sequence against it (v2_smoke.py, a synced copy of golden-paths-shared/python/v2_smoke.py).
"""
import sys

from v2_smoke import PORT, run

if __name__ == "__main__":
    sys.exit(run(["gunicorn", "-b", f"127.0.0.1:{PORT}", "main:serve()"]))
