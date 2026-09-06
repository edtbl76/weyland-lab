"""Test harness for weyland-dagster (B78 step 2, EMA-69).

Two jobs:

1. Put the project root on ``sys.path`` so ``weyland_pipeline`` resolves when pytest runs from here.
   The lane installs no package (there is no setup.py / pyproject), so the import root is explicit.

2. Provide ``load_isolated``, which imports ONE leaf module by file path, bypassing every parent
   package ``__init__``. That chain — ``weyland_pipeline/__init__.py`` imports ``sentry_sdk`` and the
   full dagster ``definitions``; ``assets/__init__.py`` imports every asset — would otherwise drag the
   entire dagster runtime into this deliberately light lane, whose only extra deps are in
   requirements-test.txt (pyarrow/pandas/numpy/minio, NOT dagster). A leaf module written with only
   absolute imports (no ``from . import ...``) loads clean in isolation and stays a normal package
   module for the runtime code that imports it relatively.
"""
import importlib.util
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def load_isolated(relpath, name="_isolated"):
    """Import ``<project-root>/relpath`` without running any parent package ``__init__``.

    The target must use only absolute imports. Raises the module's own ImportError if one of its
    (absolute) dependencies is genuinely missing — that is a real failure, not something to swallow.
    """
    path = os.path.join(_ROOT, relpath)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def parquet_read():
    """The dagster-free ``datasets_lib/parquet_read`` module, loaded in isolation."""
    return load_isolated(
        "weyland_pipeline/assets/datasets_lib/parquet_read.py", "parquet_read"
    )


@pytest.fixture
def port_components():
    """The dagster-free ``port_components`` module, loaded in isolation (stdlib-only at module scope)."""
    return load_isolated("weyland_pipeline/port_components.py", "port_components")


@pytest.fixture
def fred_parse():
    """The dagster-free ``datasets_lib/fred_parse`` module (B113), loaded in isolation (pyarrow-only)."""
    return load_isolated(
        "weyland_pipeline/assets/datasets_lib/fred_parse.py", "fred_parse"
    )


@pytest.fixture
def edgar_parse():
    """The dagster-free ``datasets_lib/edgar_parse`` module (B113 Phase 2), loaded in isolation (pyarrow-only)."""
    return load_isolated(
        "weyland_pipeline/assets/datasets_lib/edgar_parse.py", "edgar_parse"
    )


@pytest.fixture
def timeseries():
    """The dagster-free ``datasets_lib/timeseries`` hypertable-ts helper (B113), loaded in isolation."""
    return load_isolated(
        "weyland_pipeline/assets/datasets_lib/timeseries.py", "timeseries"
    )


@pytest.fixture
def mongo_encode():
    """The dagster-free ``datasets_lib/mongo_encode`` BSON-safe Arrow coercion (B113 Phase 2), isolated."""
    return load_isolated(
        "weyland_pipeline/assets/datasets_lib/mongo_encode.py", "mongo_encode"
    )


@pytest.fixture
def edgar_text_parse():
    """The dagster-free ``datasets_lib/edgar_text_parse`` 10-K section chunker (B113 Phase 3), isolated."""
    return load_isolated(
        "weyland_pipeline/assets/datasets_lib/edgar_text_parse.py", "edgar_text_parse"
    )


@pytest.fixture
def market_parse():
    """The dagster-free ``datasets_lib/market_parse`` OHLCV shaper (B113 Phase 4), loaded in isolation."""
    return load_isolated(
        "weyland_pipeline/assets/datasets_lib/market_parse.py", "market_parse"
    )


@pytest.fixture
def ml_targets():
    """The dagster-free ``datasets_lib/ml_targets`` forward-target helper (B113 Phase 5), isolated."""
    return load_isolated(
        "weyland_pipeline/assets/datasets_lib/ml_targets.py", "ml_targets"
    )


@pytest.fixture
def land_core():
    """The dagster-free ``datasets_lib/land_core`` — the write/fail-closed heart of the land-asset
    factory (B158 follow-up B), loaded in isolation (pyarrow-only, no dagster/minio)."""
    return load_isolated(
        "weyland_pipeline/assets/datasets_lib/land_core.py", "land_core"
    )


@pytest.fixture
def domain_job_plan():
    """The dagster-free ``datasets_lib/domain_job_plan`` — the single-sourced land/transform/hydrate job
    plan for a domain (B158 follow-up C), loaded in isolation (stdlib-only)."""
    return load_isolated(
        "weyland_pipeline/assets/datasets_lib/domain_job_plan.py", "domain_job_plan"
    )


@pytest.fixture
def collect():
    """The dagster-free ``assets/_collect`` autodiscovery helpers (B158 follow-up F), loaded in
    isolation — no dagster, so the collection loop logic is testable against fake asset/check types
    that mirror the ``AssetChecksDefinition <: AssetsDefinition`` subclass relationship."""
    return load_isolated("weyland_pipeline/assets/_collect.py", "_collect")


@pytest.fixture
def lakefs_repo():
    """The ``datasets_lib/lakefs_repo`` bootstrap (B158 follow-up D), loaded in isolation. Module scope is
    stdlib-only (the lakefs SDK + io are lazy inside ensure_repo), so ``storage_namespace_for`` is testable
    here; ensure_repo itself is validated live against lakeFS."""
    return load_isolated(
        "weyland_pipeline/assets/datasets_lib/lakefs_repo.py", "lakefs_repo"
    )
