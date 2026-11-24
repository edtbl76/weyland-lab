"""B243 SEED (TEMPORARY, EMA-342): the test that catches the seeded defect in scripts/lib/b243_seed_bug.py."""
import importlib.util
import pathlib

_spec = importlib.util.spec_from_file_location(
    "b243_seed_bug", pathlib.Path(__file__).resolve().parents[1] / "lib" / "b243_seed_bug.py")
seed = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seed)


def test_an_hour_has_sixty_minutes():
    assert seed.minutes_in(1) == 60
    assert seed.minutes_in(2.5) == 150
