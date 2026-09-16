"""Tests for datasets_lib/io.py's env-derived endpoint config — the small pure helpers that decide where every
dataset lands (lakeFS endpoint, branch, raw prefix). A wrong branch or prefix silently writes bronze data to the
wrong place. Loaded in isolation under a distinct module name so the leaf-test harness's `io` stub can't shadow
the real module; io.py imports `from minio import Minio` at module scope (a declared test dep) but the helpers
under test never touch minio.
"""
import importlib.util
import os

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # weyland-dagster/
_IO = os.path.join(_ROOT, "weyland_pipeline", "assets", "datasets_lib", "io.py")


@pytest.fixture(scope="module")
def io_mod():
    spec = importlib.util.spec_from_file_location("datasets_lib_io_real", _IO)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_endpoint_defaults_and_env_override(io_mod, monkeypatch):
    monkeypatch.delenv("LAKEFS_ENDPOINT", raising=False)
    assert io_mod.endpoint() == "http://lakefs.data-mesh.svc.cluster.local:8000"
    monkeypatch.setenv("LAKEFS_ENDPOINT", "https://lakefs.example:9000")
    assert io_mod.endpoint() == "https://lakefs.example:9000"


def test_branch_defaults_to_main_and_env_override(io_mod, monkeypatch):
    monkeypatch.delenv("LAKEFS_BRANCH", raising=False)
    assert io_mod.branch() == "main"
    monkeypatch.setenv("LAKEFS_BRANCH", "experiment")
    assert io_mod.branch() == "experiment"


def test_raw_prefix_tracks_branch(io_mod, monkeypatch):
    monkeypatch.setenv("LAKEFS_BRANCH", "main")
    assert io_mod.raw_prefix() == "main/raw/"
    monkeypatch.setenv("LAKEFS_BRANCH", "dev")
    assert io_mod.raw_prefix() == "dev/raw/"
