"""B243 SEED (TEMPORARY — remove after the seeded test night, EMA-342; owner approved "All five", 2026-11-24).

`b243_seed_job` (definitions.py) fails its first run, as a transient upstream error would, and passes when it is
re-executed from failure (a re-execution has a parent run). That lets the 05:30 morning remediation prove its
allowlisted `dagster-reexecute-run` action end to end. No schedule: launched once by hand for the test night.
Stdlib only, so the light test lane can test it (tests/test_b243_seed.py).
"""


class SeedFailure(Exception):
    pass


def seed_outcome(parent_run_id):
    if parent_run_id is None:
        raise SeedFailure("upstream index answered HTTP 503 Service Unavailable "
                          "(B243 seed: a transient failure; re-executing this run from failure passes)")
    return f"B243 seed: the re-execution of {parent_run_id} passes"
