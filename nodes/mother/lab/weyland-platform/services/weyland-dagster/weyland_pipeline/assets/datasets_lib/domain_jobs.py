"""build_domain_jobs — generate a domain's operate-plane jobs from its DomainConfig (B158 follow-up C).

The audit found the operate edge hand-authored per domain: a land / transform / hydrate job trio that
enumerated land assets by literal string in two places (the land job and the transform exclusion), and
finance had none — which is why its land assets slipped into the 15-min ingestion cron unnoticed.

``build_domain_jobs(cfg)`` derives all three from the single-sourced ``domain_job_plan``: the land job is
``cfg.land_deps``, the transform job is the domain group MINUS exactly those land assets (so land re-fetch
never runs in the transform), and the hydrate job is the Tier-2 stores group. Because the land job and the
transform exclusion come from the one ``land_deps`` list the transform assets already ``deps`` on, the
split cannot drift. The pure plan is unit-tested in ``domain_job_plan``; this adds only the dagster wiring.
"""
from collections import namedtuple

from dagster import (
    AssetSelection,
    DefaultScheduleStatus,
    ScheduleDefinition,
    define_asset_job,
)

from . import domain_job_plan as _plan

DomainJobs = namedtuple("DomainJobs", "land_job transform_job hydrate_job land_schedule")


def build_domain_jobs(cfg, *, serial_exec, hydrate_exec, land_cron=None,
                      land_status=DefaultScheduleStatus.STOPPED, timezone="America/New_York"):
    """Build a domain's (land_job, transform_job, hydrate_job, land_schedule) from its DomainConfig.

    ``serial_exec`` / ``hydrate_exec`` are the run-config dicts the domain jobs share with music/health
    (transform serialized to 1×-peak memory, hydrate 2–3-way). ``land_cron`` (optional) attaches a land
    schedule, STOPPED by default — the land data is static snapshots, run on demand until a domain opts in.
    """
    p = _plan.domain_job_plan(cfg.domain, cfg.group_name, cfg.land_deps)

    land_job = define_asset_job(
        name=p["land"]["name"],
        selection=AssetSelection.assets(*p["land"]["assets"]),
    )
    transform_job = define_asset_job(
        name=p["transform"]["name"],
        config=serial_exec,
        selection=AssetSelection.groups(p["transform"]["group"])
        - AssetSelection.assets(*p["transform"]["exclude"]),
    )
    hydrate_job = define_asset_job(
        name=p["hydrate"]["name"],
        config=hydrate_exec,
        selection=AssetSelection.groups(p["hydrate"]["group"]),
    )
    land_schedule = None
    if land_cron:
        land_schedule = ScheduleDefinition(
            job=land_job,
            cron_schedule=land_cron,
            name=p["land_schedule"]["name"],
            execution_timezone=timezone,
            default_status=land_status,
        )
    return DomainJobs(land_job, transform_job, hydrate_job, land_schedule)
