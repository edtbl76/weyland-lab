"""The land-asset factory (B158 follow-up B) — the paved ingestion edge.

Before this, every land asset (FRED, EDGAR, EDGAR-text, market …) re-typed the same ~50-line scaffold:
skip-if-fresh, fetch+shape, FAIL CLOSED on an empty land, minio client, per-table parquet write, Output
+ metadata. Only the fetch+shape is genuinely source-specific. ``build_land_asset`` generates the rest
from one ``produce`` callable, so onboarding a new source is a ``produce()`` plus a one-line factory call
(see the finance landers for the before/after). The pure write/fail-closed decisions live in the
dagster-free ``land_core`` (unit-tested in isolation); this module adds only the ``@asset`` + io wiring.
"""
from dagster import MetadataValue, Output, asset

from . import io, lakefs_repo, land_core
from .freshness import RefreshConfig, should_skip


def build_land_asset(name, repo, produce, *, group, description=""):
    """Build a land ``@asset``.

    ``produce(context)`` does the source-specific work and returns either ``(tables, detail)`` or
    ``(tables, detail, extra)``: ``tables`` is a ``{table_name: pyarrow.Table}`` map (each lands at
    ``<repo>/raw/<name>/<name>.parquet``), ``detail`` is a per-item dict that becomes the asset's Output
    value + ``detail`` metadata, and the optional ``extra`` is a plain ``{key: json-able}`` dict of extra
    diagnostic metadata (e.g. EDGAR's ``concept_present``), rendered as JSON metadata. Everything else —
    the freshness skip (bypass with ``{"force": true}``), the fail-closed on zero rows, the minio put per
    table, and the row-count metadata — is generated here.
    """

    @asset(name=name, group_name=group, description=description)
    def _land(context, config: RefreshConfig) -> Output[dict]:
        if should_skip(context, config):
            return Output({"skipped": True}, metadata={"skipped": MetadataValue.bool(True)})

        produced = produce(context)
        tables, detail = produced[0], produced[1]
        extra = produced[2] if len(produced) > 2 else {}
        if land_core.total_rows(tables) == 0:
            # Fail closed — a land that shaped no rows raises rather than committing an empty raw layer
            # that reads downstream as a successful-but-empty dataset.
            raise RuntimeError(f"{name} produced zero rows across all tables: {detail}")

        # Self-provision the lakeFS repo before the first write (B158 follow-up D). Idempotent — a no-op
        # once the repo exists — so a new domain's first land creates its repo instead of failing at
        # runtime against a repo an operator forgot to pre-create.
        lakefs_repo.ensure_repo(repo)

        client = io.client()

        def put(key, data):
            io.put_raw(client, repo, key, data, "application/vnd.apache.parquet")

        written = land_core.write_tables(put, tables)
        context.log.info(
            f"{name}: landed " + ", ".join(f"{k} ({v:,} rows)" for k, v in written.items())
        )
        # sources_ok = per-item entries that fetched without error (an int outcome; a failed item is a
        # string "ERROR: …"). Reproduces the old series_ok/tickers_ok metric generically.
        sources_ok = sum(1 for v in detail.values() if isinstance(v, int))
        md = {f"{k}_rows": MetadataValue.int(v) for k, v in written.items()}
        md["sources_ok"] = MetadataValue.int(sources_ok)
        for k, v in extra.items():
            md[k] = MetadataValue.json(v)
        md["detail"] = MetadataValue.json(detail)
        return Output(detail, metadata=md)

    return _land
