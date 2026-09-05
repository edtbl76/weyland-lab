"""Tests for the dagster-free ``domain_job_plan`` (B158 follow-up C).

The one property that matters: the land job's assets and the transform job's exclusion come from the
SAME ``land_deps`` list, so the split that let finance's land assets get swept into the 15-min ingestion
cron cannot happen here — it is single-sourced. Also pins the job/schedule names the runtime + docs use.
"""

_LAND = ("datasets_finance_fred_land", "datasets_finance_edgar_land", "datasets_finance_market_land")


def test_land_assets_and_transform_exclusion_are_the_same_list(domain_job_plan):
    p = domain_job_plan.domain_job_plan("finance", "datasets_finance", _LAND)
    # THE drift-proof invariant: what the land job runs is exactly what the transform job excludes.
    assert p["land"]["assets"] == p["transform"]["exclude"]
    assert p["land"]["assets"] == list(_LAND)


def test_transform_and_hydrate_target_the_right_groups(domain_job_plan):
    p = domain_job_plan.domain_job_plan("finance", "datasets_finance", _LAND)
    assert p["transform"]["group"] == "datasets_finance"
    assert p["hydrate"]["group"] == "datasets_finance_stores"


def test_job_and_schedule_names(domain_job_plan):
    p = domain_job_plan.domain_job_plan("finance", "datasets_finance", ())
    assert p["land"]["name"] == "weyland_datasets_finance_land_job"
    assert p["transform"]["name"] == "weyland_datasets_finance_transform_job"
    assert p["hydrate"]["name"] == "weyland_datasets_finance_hydrate_job"
    assert p["land_schedule"]["name"] == "weyland_datasets_finance_land_schedule"


def test_empty_land_deps_yields_empty_land_and_exclusion(domain_job_plan):
    # a domain with no landers (all-derived) still gets a coherent plan; nothing to exclude from transform.
    p = domain_job_plan.domain_job_plan("music", "datasets_music", ())
    assert p["land"]["assets"] == []
    assert p["transform"]["exclude"] == []
