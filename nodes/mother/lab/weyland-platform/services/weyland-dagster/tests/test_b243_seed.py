"""B243 seeded test night (TEMPORARY, EMA-342): the Dagster seed job fails its first run, as a transient error would,
and passes when re-executed from failure, so the morning remediation's allowlisted `dagster-reexecute-run` can be
proven end to end. Stdlib only (the light lane has no dagster): the decision is a pure function of the run's parent.
"""
import importlib.util
import pathlib

import pytest

_spec = importlib.util.spec_from_file_location(
    "b243_seed", pathlib.Path(__file__).resolve().parent.parent / "weyland_pipeline" / "b243_seed.py")
b243_seed = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(b243_seed)


def test_a_first_run_fails_with_a_transient_looking_error():
    with pytest.raises(b243_seed.SeedFailure, match="503"):
        b243_seed.seed_outcome(parent_run_id=None)


def test_a_re_execution_passes():
    assert "passes" in b243_seed.seed_outcome(parent_run_id="0f8e7d6c-1234-4abc-9def-0123456789ab")
