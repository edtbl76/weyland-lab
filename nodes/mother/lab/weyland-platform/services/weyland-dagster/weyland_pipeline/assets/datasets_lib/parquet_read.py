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


def resolve_text_columns(requested, available):
    """Fail-closed resolution of a text spec's columns against what the source actually has.

    Returns the present subset in requested order, but RAISES when none are present. A text spec that
    resolves to nothing would otherwise embed empty strings for every row and report a successful
    hydration — the silent-empty-vector bug step 1 proved is real (a column copied from stale field
    docs, e.g. ``categories_fr``, which the OFF silver does not have). The message names both the
    requested set and a sample of what does exist, so the mismatch is obvious.
    """
    present = [c for c in requested if c in available]
    if not present:
        raise ValueError(
            f"text columns {list(requested)} are all absent from the source; "
            f"available columns include {sorted(available)[:15]}"
        )
    return present


def read_capped(path, columns, filter_col=None, cap=None, batch_size=50_000):
    """Projected, capped, streaming read of ONE parquet file — the bounded replacement for the
    whole-file ``pd.read_parquet`` in ``loaders._build_vectors`` that OOMs on OFF's 4.5M × 211
    all-string file (materialising ~45 GB before any cap can apply).

    Reads only the columns in ``columns`` that exist — parquet is columnar, so the other ~205 are
    never touched and an absent requested column simply drops out. Rows whose ``filter_col`` is empty
    are removed during iteration (``na_filter=False`` at ingest makes "missing" the empty string, not
    null); ``cap``, when set, stops the read the moment that many rows are collected. Peak memory is a
    function of ``batch_size × len(columns)`` — independent of the source's row count or width, which
    is what retires the OOM for OFF and every future large source.

    ``columns=None`` reads every column (the un-projected path, unchanged behaviour). Fail-closed: a
    ``filter_col`` absent from the file RAISES rather than silently passing every row. Returns a pandas
    DataFrame carrying exactly the projected columns.
    """
    import pandas as pd
    import pyarrow.parquet as pq

    parquet = pq.ParquetFile(path)
    available = set(parquet.schema_arrow.names)

    if filter_col is not None and filter_col not in available:
        raise ValueError(
            f"filter column {filter_col!r} is not in {path}; "
            f"available columns include {sorted(available)[:15]}"
        )

    projection = None
    read_cols = None
    if columns is not None:
        projection = [c for c in columns if c in available]
        read_cols = list(projection)
        if filter_col and filter_col not in read_cols:
            read_cols.append(filter_col)

    frames = []
    collected = 0
    for batch in parquet.iter_batches(batch_size=batch_size, columns=read_cols):
        part = batch.to_pandas()
        if filter_col:
            part = part[part[filter_col].astype(str).str.len() > 0]
        if cap is not None and collected + len(part) >= cap:
            frames.append(part.iloc[: cap - collected])
            collected = cap
            break
        frames.append(part)
        collected += len(part)

    if frames:
        df = pd.concat(frames, ignore_index=True)
    else:
        df = pd.DataFrame(columns=read_cols or [])

    if projection is not None:
        # Return only the projected columns — drops filter_col if it was read solely to filter on.
        df = df[projection]
    return df
