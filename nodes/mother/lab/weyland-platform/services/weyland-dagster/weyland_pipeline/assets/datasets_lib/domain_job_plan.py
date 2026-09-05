"""Dagster-free plan for a domain's operate-plane jobs (B158 follow-up C).

The operate edge was the other hand-assembly bracket the B158 audit found: every domain's jobs were
hand-authored, enumerating land assets by literal string in BOTH the land job and the transform job's
exclusion — and finance had none at all, which is how its land assets were swept into the 15-min
ingestion cron (they appeared in no per-domain job to be reasoned about).

This derives the land / transform / hydrate job selections from ONE input: ``land_deps`` — the exact
tuple the DomainConfig already carries and the transform assets already ``deps`` on. Because the land
job's assets and the transform job's exclusion are the SAME list, the split cannot drift: single-sourced
by construction. ``domain_jobs.build_domain_jobs`` turns this plain-data plan into dagster jobs; keeping
the derivation here (no dagster import) lets it test in isolation like the ``*_parse`` leaves.
"""


def domain_job_plan(domain, group_name, land_deps):
    """Return the plan (plain data) for a domain's three jobs + its land schedule.

    - ``land``: the ``land_deps`` assets (fetch external sources → raw parquet).
    - ``transform``: the domain's transform group MINUS exactly those land assets (silver + gold).
    - ``hydrate``: the domain's Tier-2 stores group.
    The land-job assets and the transform exclusion are the SAME list, so they cannot diverge.
    """
    land = list(land_deps)
    return {
        "land": {"name": f"weyland_datasets_{domain}_land_job", "assets": land},
        "transform": {
            "name": f"weyland_datasets_{domain}_transform_job",
            "group": group_name,
            "exclude": land,
        },
        "hydrate": {
            "name": f"weyland_datasets_{domain}_hydrate_job",
            "group": f"datasets_{domain}_stores",
        },
        "land_schedule": {"name": f"weyland_datasets_{domain}_land_schedule"},
    }
