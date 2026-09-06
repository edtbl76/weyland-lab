"""Pure autodiscovery collection helpers for ``assets/__init__.py`` (B158 follow-up F).

Kept dagster-free and side-effect-free so the LOOP LOGIC is unit-testable in isolation
(``conftest.load_isolated``) without the dagster runtime. The trap these guard against is a
runtime-type fact, not a logic slip: dagster's ``AssetChecksDefinition`` SUBCLASSES
``AssetsDefinition``, so a standalone asset check satisfies ``isinstance(x, AssetsDefinition)``.
The caller's ``is_asset`` predicate must therefore EXCLUDE checks, and ``collect_assets`` must apply
that predicate to list ELEMENTS too — not a hardcoded ``isinstance``. Getting the ``elif`` wrong
registered every imported ``*_checks`` list as assets AND as checks, so each check key was defined
twice → ``DagsterInvalidDefinitionError: Duplicate asset check key`` at code-server load (took the
dagster code server down on 2026-09-05; caught by the ship SMOKE/TXN gate). ``tests/test_collect.py``
reproduces the subclass relationship with fakes and pins both functions.
"""


def collect_assets(values, is_asset):
    """Every value the predicate accepts, plus every list/tuple whose items ALL pass it.

    ``is_asset`` is applied to list elements as well as top-level values, so a caller that excludes
    asset checks from ``is_asset`` never lets a ``*_checks`` list leak in through the list branch.
    """
    out = []
    for v in values:
        if is_asset(v):
            out.append(v)
        elif isinstance(v, (list, tuple)) and v and all(is_asset(x) for x in v):
            out.extend(v)
    return out


def collect_checks(items):
    """Flatten every ``(name, value)`` whose name ends in ``_checks`` and whose value is a list/tuple."""
    out = []
    for name, v in items:
        if name.endswith("_checks") and isinstance(v, (list, tuple)):
            out.extend(v)
    return out
