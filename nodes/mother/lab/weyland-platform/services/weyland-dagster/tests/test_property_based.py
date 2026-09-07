"""Property-based tests (B152 category 5) — invariants over the pure datasets_lib leaves via hypothesis.

Example-based tests check specific inputs; these assert INVARIANTS across generated inputs. The leaves are
dagster-free, so this runs in the slim no-dagster lane. Modules are loaded by file path (the load_isolated
pattern) at import time — not via a fixture — so hypothesis's generated args don't collide with a
function-scoped fixture."""
import importlib.util
import pathlib

from hypothesis import given
from hypothesis import strategies as st

_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _load(relpath: str, name: str):
    spec = importlib.util.spec_from_file_location(name, _ROOT / relpath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


domain_job_plan = _load("weyland_pipeline/assets/datasets_lib/domain_job_plan.py", "pb_domain_job_plan")
_collect = _load("weyland_pipeline/assets/_collect.py", "pb_collect")


# ── domain_job_plan: the land/transform split is single-sourced and CANNOT drift ──────────────────

_asset_names = st.lists(st.text(min_size=1, max_size=24), max_size=10, unique=True)
_domains = st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=1, max_size=12)


@given(domain=_domains, deps=_asset_names)
def test_land_and_transform_exclusion_are_the_same_list(domain, deps):
    """The property whose violation swept finance's land into the 15-min cron: for ANY land_deps,
    the transform job's exclusion equals the land job's assets — so the split can never diverge."""
    plan = domain_job_plan.domain_job_plan(domain, f"datasets_{domain}", deps)
    assert plan["land"]["assets"] == plan["transform"]["exclude"]
    assert plan["land"]["assets"] == list(deps)


@given(domain=_domains, deps=_asset_names)
def test_every_job_name_embeds_the_domain(domain, deps):
    plan = domain_job_plan.domain_job_plan(domain, f"datasets_{domain}", deps)
    for key in ("land", "transform", "hydrate", "land_schedule"):
        assert domain in plan[key]["name"]


# ── _collect: assets and checks never overlap; checks-flatten only *_checks lists ─────────────────


class _Asset:
    pass


class _Check(_Asset):  # mirrors dagster: AssetChecksDefinition <: AssetsDefinition
    pass


def _is_asset(x) -> bool:
    return isinstance(x, _Asset) and not isinstance(x, _Check)


# a value is a bare asset, a bare check, a list of assets, or a list of checks (mixed lists excluded)
_things = st.lists(
    st.one_of(
        st.builds(_Asset),
        st.builds(_Check),
        st.lists(st.builds(_Asset), max_size=4),
        st.lists(st.builds(_Check), max_size=4),
    ),
    max_size=12,
)


@given(values=_things)
def test_collect_assets_never_yields_a_check(values):
    """No matter the input mix, a check (AssetChecksDefinition-like) never lands in the asset set."""
    assets = _collect.collect_assets(values, _is_asset)
    assert all(_is_asset(a) for a in assets)
    assert not any(isinstance(a, _Check) for a in assets)


_named_items = st.lists(
    st.tuples(
        st.text(min_size=1, max_size=20),
        st.one_of(st.lists(st.integers(), max_size=4), st.text(), st.integers(), st.none()),
    ),
    max_size=10,
)


@given(items=_named_items)
def test_collect_checks_flattens_only_named_list_values(items):
    """collect_checks flattens exactly the (name endswith '_checks' AND value is a list/tuple) entries."""
    result = _collect.collect_checks(items)
    expected = [x for name, v in items if name.endswith("_checks") and isinstance(v, (list, tuple)) for x in v]
    assert result == expected
