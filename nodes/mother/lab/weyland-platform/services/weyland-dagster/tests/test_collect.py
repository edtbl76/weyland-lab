"""Regression guard for the autodiscovery collection logic (B158 follow-up F).

The dagster code server crashed on 2026-09-05 with
``DagsterInvalidDefinitionError: Duplicate asset check key datasets_music_parquet/no_failures``.
Cause: ``AssetChecksDefinition`` SUBCLASSES ``AssetsDefinition``, so the ``all_assets`` collector's
list branch (``all(isinstance(x, AssetsDefinition) ...)``) slurped every imported ``datasets_*_checks``
list into ``all_assets`` in ADDITION to ``all_asset_checks`` — each check key defined twice.

These tests reproduce that subclass relationship with fakes (``_Check`` extends ``_Asset``), so the
loop logic is pinned in the fast test lane the original bug slipped past: that lane installs no
dagster, so it could never build the real ``Definitions`` where the duplicate is detected. The whole
point is that the guard must live where dagster does NOT."""


class _Asset:
    pass


class _Check(_Asset):  # mirrors dagster: AssetChecksDefinition <: AssetsDefinition
    pass


def _is_asset(x):
    """The predicate assets/__init__.py must use — a real asset, and NOT a check."""
    return isinstance(x, _Asset) and not isinstance(x, _Check)


def test_a_list_of_checks_is_not_collected_as_assets(collect):
    a = _Asset()
    chk = _Check()
    # `a` is a real asset; `[chk]` mirrors an imported `datasets_music_checks` list.
    assets = collect.collect_assets([a, [chk]], _is_asset)
    assert a in assets
    assert chk not in assets  # the exact leak that duplicated the check key
    assert assets == [a]


def test_a_bare_check_is_not_collected_as_an_asset(collect):
    assert collect.collect_assets([_Check()], _is_asset) == []


def test_real_assets_and_asset_lists_are_collected(collect):
    a, b, c = _Asset(), _Asset(), _Asset()
    assert collect.collect_assets([a, [b, c]], _is_asset) == [a, b, c]


def test_a_mixed_list_is_rejected_whole(collect):
    # all-or-nothing: a list with any non-asset element is not extended (matches the original guard).
    assert collect.collect_assets([[_Asset(), object()]], _is_asset) == []


def test_collect_checks_flattens_named_lists_only(collect):
    items = [
        ("datasets_music_checks", [1, 2]),
        ("datasets_health_checks", (3,)),
        ("all_assets", [object()]),                  # not a *_checks name
        ("datasets_finance_checks", "not-a-list"),   # right name, wrong type
    ]
    assert collect.collect_checks(items) == [1, 2, 3]


def test_assets_and_checks_are_disjoint(collect):
    """The property whose violation crashed the load: nothing is registered as both."""
    a = _Asset()
    music_checks = [_Check(), _Check()]
    g = [("parquet", a), ("datasets_music_checks", music_checks)]
    assets = collect.collect_assets([v for _, v in g], _is_asset)
    checks = collect.collect_checks(g)
    assert not ({id(x) for x in assets} & {id(x) for x in checks})
    assert a in assets and all(c in checks for c in music_checks)
