"""ge_validate.py — the GE runner's re-run behaviour (B227 follow-on, 2026-10-25).

The GE context is a FILE context on the ge-data PVC, so it outlives every run. The runner created each suite with
`get_validator(create_expectation_suite_with_name=...)`, which REFUSES an existing suite: the first run worked and every
run after it died on its first table ("An ExpectationSuite named ge_iceberg_dbt_mart_country_health already exists"),
seen on runs before and after B227's ship. These run in the isolated GE venv (requirements-ge.txt); the main Python lane
has no great_expectations and skips them (collected with this project's other tests, so the lane still runs real
tests here). Run them for real in the GE venv: runbooks/great-expectations.md § Tests.
"""
import os
import sqlite3
import sys

import pytest

gx = pytest.importorskip("great_expectations")
from great_expectations.profile.user_configurable_profiler import UserConfigurableProfiler  # noqa: E402

# ge_validate.py lives in ge/ (the isolated venv runs it as a script), so import it by path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ge"))
import ge_validate  # noqa: E402


@pytest.fixture
def ctx_and_batch(tmp_path):
    db = tmp_path / "t.db"
    con = sqlite3.connect(db)
    con.execute("create table t (a integer, b text)")
    con.executemany("insert into t values (?, ?)", [(i, f"v{i % 3}") for i in range(20)])
    con.commit()
    con.close()
    ctx = gx.get_context(mode="file", project_root_dir=str(tmp_path / "ge"))
    ds = ctx.sources.add_or_update_sqlite("s", connection_string=f"sqlite:///{db}")
    asset = ds.add_table_asset(name="t", table_name="t")
    return ctx, asset.build_batch_request()


def _profile(validator):
    UserConfigurableProfiler(profile_dataset=validator).build_suite()
    validator.save_expectation_suite(discard_failed_expectations=False)


def test_the_old_create_only_call_fails_on_a_rerun(ctx_and_batch):
    # pins the bug in THIS GE version: what the runner used to do cannot run twice on a persistent context
    ctx, br = ctx_and_batch
    _profile(ctx.get_validator(batch_request=br, create_expectation_suite_with_name="ge_t"))
    with pytest.raises(Exception, match="already exists"):
        ctx.get_validator(batch_request=br, create_expectation_suite_with_name="ge_t")


def test_the_runner_reprofiles_on_every_run_without_piling_up(ctx_and_batch):
    ctx, br = ctx_and_batch
    _profile(ge_validate.suite_validator(ctx, br, "ge_t"))
    first = len(ctx.get_expectation_suite("ge_t").expectations)
    _profile(ge_validate.suite_validator(ctx, br, "ge_t"))      # the rerun that used to fail
    second = len(ctx.get_expectation_suite("ge_t").expectations)
    assert first > 0
    assert second == first                                      # a fresh suite each run, not the old one plus more
