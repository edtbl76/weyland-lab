"""broker — the asset factory. build_transform_assets(cfg) returns the 5 format assets + commit for a
domain, all sharing the readers/writers in this package. Each output format re-reads raw/ in its own
process (the asset graph IS the broker) so one bad source or a native crash is isolated to that format.
Asset names are datasets_<domain>_<format> so existing __init__/jobs/schedules references stay valid."""
import os

from dagster import MetadataValue, Output, asset

from . import io
from .readers import iter_raw_tables
from .writers import SkipTable, hydrate_iceberg, write_arrow, write_avro, write_lance, write_parquet


def build_transform_assets(cfg):
    common = dict(group_name=cfg.group_name, deps=list(cfg.land_deps))
    d = cfg.domain

    def run_format(context, write_one, allow):
        mc = io.client()
        out: dict = {}
        for table, name, t in iter_raw_tables(mc, cfg.repo, allow, context.log):
            key = f"{table}/{name}"
            try:
                write_one(mc, cfg, table, name, t)
                out[key] = f"ok ({t.num_rows}r x {t.num_columns}c)"
            except SkipTable as sk:
                out[key] = f"deferred: {sk}"
                context.log.warning(f"{key}: deferred — {sk}")
            except Exception as e:  # noqa: BLE001 — per-table resilience within a format
                out[key] = f"ERROR {type(e).__name__}: {e}"
                context.log.error(f"{key}: {e}")
        if not out:
            context.log.warning(f"no allowlisted raw tables under {cfg.repo}/raw/ — run land first")
        return Output(out, metadata={
            "ok": MetadataValue.int(sum(1 for v in out.values() if v.startswith("ok"))),
            "deferred": MetadataValue.int(sum(1 for v in out.values() if v.startswith("deferred"))),
            "detail": MetadataValue.json(out),
        })

    @asset(name=f"datasets_{d}_parquet", **common, description=f"Silver — Parquet (batch columnar) for each {d} raw table.")
    def parquet(context):
        return run_format(context, write_parquet, cfg.parquet_allow)

    @asset(name=f"datasets_{d}_arrow", **common, description=f"Silver — Arrow/Feather (IPC) for each {d} raw table.")
    def arrow(context):
        return run_format(context, write_arrow, cfg.arrow_allow)

    @asset(name=f"datasets_{d}_avro", **common, description=f"Silver — Avro (streamed, row-oriented) for each {d} raw table.")
    def avro(context):
        return run_format(context, write_avro, cfg.avro_allow)

    @asset(name=f"datasets_{d}_lance", **common, description=f"Silver — Lance (ML/vector, allowlisted) for each {d} raw table.")
    def lance(context):
        return run_format(context, write_lance, cfg.lance_allow)

    @asset(name=f"datasets_{d}_iceberg", **common, description=f"Gold — Iceberg ({cfg.namespace}.*) for each {d} raw table.")
    def iceberg(context):
        return run_format(context, hydrate_iceberg, cfg.iceberg_allow)

    @asset(
        name=f"datasets_{d}_commit",
        group_name=cfg.group_name,
        deps=[f"datasets_{d}_parquet", f"datasets_{d}_arrow", f"datasets_{d}_avro", f"datasets_{d}_lance"],
        description=f"Commit the lakeFS {cfg.repo} branch after the file writes → one version per run. Iceberg is on Nessie, not lakeFS.",
    )
    def commit(context):
        import lakefs

        lc = lakefs.Client(host=io.endpoint(), username=os.environ["LAKEFS_ACCESS_KEY_ID"], password=os.environ["LAKEFS_SECRET_ACCESS_KEY"])
        br = lakefs.Repository(cfg.repo, client=lc).branch(io.branch())
        changes = list(br.uncommitted())
        if not changes:
            context.log.info(f"lakeFS {cfg.repo}/{io.branch()}: no uncommitted changes — nothing to version")
            return Output({"committed": False, "changes": 0})
        ref = br.commit(message=f"datasets_{d} pipeline run", metadata={"producer": f"dagster:datasets_{d}"})
        cid = ref.get_commit().id
        context.log.info(f"lakeFS {cfg.repo}/{io.branch()}: committed {len(changes)} change(s) → {cid[:12]}")
        return Output(
            {"committed": True, "changes": len(changes), "commit": cid},
            metadata={"changes": MetadataValue.int(len(changes)), "commit": MetadataValue.text(cid)},
        )

    return [parquet, arrow, avro, lance, iceberg, commit]
