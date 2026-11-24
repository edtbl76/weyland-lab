"""b243_seed_bug.py — B243 SEED (TEMPORARY, EMA-342; owner approved "All five", 2026-11-24).

A small helper that carries one defect on purpose, so the nightly CI's test-python step fails and the 05:30 morning
remediation can prove its fix-branch path (an auto-fix/<date>-<slug> branch that passes scripts/local-gates.py).
Removed, with its test, after the seeded test night.
"""


def minutes_in(hours: float) -> float:
    """How many minutes are in `hours` hours."""
    return hours * 50
