"""Test harness for scan-suite/scan.py.

scan.py is a flat script that, at import, reads SCAN_SRC/SCAN_OUT/SCAN_TARGET/PORT_INGEST_URL from the env AND
runs ``os.makedirs(OUT)``. So before it loads we point OUT/SRC at a writable tmp dir and ensure PORT_INGEST_URL
is UNSET (so ``post()`` builds the payload but skips the network). Each tool runner is run+parse+post; the tests
stub ``sh``/``load``/``subprocess`` to feed fixture tool-output JSON and capture ``post()`` to assert the REAL
severity-mapped counts — the actual correctness of the scanner, with no tool executed and no network.
"""
import os
import sys
import tempfile

import pytest

_ROOT = os.path.dirname(os.path.abspath(__file__))
_TMP = tempfile.mkdtemp(prefix="scan-suite-test-")
os.environ["SCAN_OUT"] = _TMP            # scan.py does os.makedirs(OUT) at import — must be writable
os.environ.setdefault("SCAN_SRC", _TMP)
os.environ.setdefault("SCAN_TARGET", "test-repo")
os.environ.pop("PORT_INGEST_URL", None)  # PORT_URL=None → post() skips the POST, no network

if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


@pytest.fixture
def scan():
    """Fresh import of scan.py with a cleared RESULTS list (module-level accumulator)."""
    import importlib
    sys.modules.pop("scan", None)
    mod = importlib.import_module("scan")
    mod.RESULTS.clear()
    return mod


@pytest.fixture
def captured_posts(scan, monkeypatch):
    """Capture (tool, counts) that each runner posts, without touching the network."""
    posts = []
    monkeypatch.setattr(scan, "sh", lambda *a, **k: None)            # never run a real tool
    monkeypatch.setattr(scan, "post", lambda tool, c: posts.append((tool, dict(c))))
    return posts
