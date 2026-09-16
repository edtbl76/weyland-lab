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


@pytest.fixture
def loaders():
    """The ``datasets_lib/loaders`` store-loaders. Unlike the leaf modules, loaders uses RELATIVE imports
    (``from . import io``) and imports dagster, so ``load_isolated`` can't reach it. Instead we register a
    synthetic ``weyland_pipeline.assets.datasets_lib`` package whose ``__path__`` points at the real dir (so
    the relative imports resolve to the real sibling files), and STUB the heavy edges: dagster (module-scope
    ``MetadataValue``/``Output``/``asset``), the ``@traced_load`` otel span decorator (→ identity), and the
    minio-backed ``io`` sibling. What's left is fully exercisable with no dagster runtime, no minio, no live
    store — the SQL/CQL/Cypher identifier-safety quoting, the multi-value list parser, and the GraphSpec→
    Cypher compiler. The store-write functions themselves are validated live against the real stores.
    """
    import importlib
    import types

    pkg = "weyland_pipeline.assets.datasets_lib"
    dl_dir = os.path.join(_ROOT, "weyland_pipeline", "assets", "datasets_lib")
    added = []

    def _put(name, module):
        sys.modules[name] = module
        added.append(name)

    class _Any:  # a permissive stand-in for dagster's MetadataValue/Output (never called in these tests)
        def __call__(self, *a, **k): return self
        def __getattr__(self, _n): return self

    dagster = types.ModuleType("dagster")
    dagster.MetadataValue = _Any()
    dagster.Output = _Any()

    def _asset(*a, **k):  # supports both @asset and @asset(...)
        if a and callable(a[0]) and not k:
            return a[0]
        return lambda f: f

    dagster.asset = _asset
    _put("dagster", dagster)

    wp = types.ModuleType("weyland_pipeline"); wp.__path__ = []
    _put("weyland_pipeline", wp)
    otel = types.ModuleType("weyland_pipeline._otel"); otel.traced_load = lambda f: f
    _put("weyland_pipeline._otel", otel)
    assets = types.ModuleType("weyland_pipeline.assets"); assets.__path__ = []
    _put("weyland_pipeline.assets", assets)
    dl = types.ModuleType(pkg); dl.__path__ = [dl_dir]
    _put(pkg, dl)
    io_stub = types.ModuleType(pkg + ".io")            # minio-backed; the pure helpers never touch it
    _put(pkg + ".io", io_stub)
    me = types.ModuleType(pkg + ".mongo_encode"); me.to_bson_encodable = lambda x: x
    _put(pkg + ".mongo_encode", me)
    ts = types.ModuleType(pkg + ".timeseries"); ts.hypertable_ts = lambda *a, **k: None
    _put(pkg + ".timeseries", ts)

    sys.modules.pop(pkg + ".loaders", None)
    module = importlib.import_module(pkg + ".loaders")
    yield module
    for name in added + [pkg + ".loaders"]:
        sys.modules.pop(name, None)


@pytest.fixture
def datahub_emit():
    """The DataHub metadata emitter (``weyland_pipeline/datahub_emit.py``), imported with dagster and the asset
    graph stubbed but the REAL acryl-datahub SDK present — so its builders produce genuine
    MetadataChangeProposalWrapper aspects the tests assert against (not stubbed objects). ``build_mcps`` and the
    ``emit_*`` functions are driven with fixture inputs — monkeypatch ``_asset_info``, or pass a capturing emitter
    that records the MCPs instead of POSTing them. The live DataHub REST round-trip is validated in the running
    system; here we test the payload-building logic that decides WHAT gets emitted.
    """
    import importlib.util
    import types

    added = []

    def _put(name, module):
        sys.modules[name] = module
        added.append(name)

    class _Any:
        def __call__(self, *a, **k): return self
        def __getattr__(self, _n): return self

    dagster = types.ModuleType("dagster")
    dagster.AssetKey = _Any(); dagster.MetadataValue = _Any(); dagster.Output = _Any()
    dagster.asset = lambda *a, **k: (a[0] if a and callable(a[0]) and not k else (lambda f: f))
    _put("dagster", dagster)

    root = os.path.join(_ROOT, "weyland_pipeline")
    wp = types.ModuleType("weyland_pipeline"); wp.__path__ = [root]
    _put("weyland_pipeline", wp)
    assets = types.ModuleType("weyland_pipeline.assets"); assets.all_assets = []
    _put("weyland_pipeline.assets", assets)

    spec = importlib.util.spec_from_file_location(
        "datahub_emit_isolated", os.path.join(root, "datahub_emit.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop("datahub_emit_isolated", None)
    for name in added:
        sys.modules.pop(name, None)
