"""Dagster-free parquet-read helpers for the vector loader (B78, EMA-69).

Deliberately self-contained: ONLY absolute imports, no ``from . import ...`` and no dagster. That is
what lets the test lane load this module in isolation (see the ``load_isolated`` helper in the
service's conftest) without the package ``__init__`` chain pulling the whole dagster runtime into an
intentionally light lane. ``_build_vectors`` in ``loaders.py`` consumes these helpers.

Step 2 (this commit) seeds ``needed_columns``; the projected + capped ``iter_batches`` read and the
fail-closed column resolution land in step 3.
"""


def needed_columns(spec):
    """The ordered, de-duplicated list of columns a vector spec references — the exact projection the
    read must pull off the parquet and nothing else. This is what turns a whole-file read of OFF's 211
    columns into a read of the ~6 the spec names.

    Order: ``text``, then ``numeric``, then the ``id`` and ``filter`` scalars, then ``payload``. Any
    absent key contributes nothing, so ``needed_columns({})`` is ``[]``. First-seen order is preserved
    and duplicates collapse (``product_name`` commonly appears in ``text``, ``filter`` AND ``payload``).
    """
    ordered = []
    ordered += list(spec.get("text") or [])
    ordered += list(spec.get("numeric") or [])
    for scalar_key in ("id", "filter"):
        value = spec.get(scalar_key)
        if value:
            ordered.append(value)
    ordered += list(spec.get("payload") or [])

    seen = set()
    projection = []
    for column in ordered:
        if column not in seen:
            seen.add(column)
            projection.append(column)
    return projection
