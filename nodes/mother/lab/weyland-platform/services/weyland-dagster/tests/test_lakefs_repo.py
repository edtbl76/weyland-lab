"""Tests for ``lakefs_repo`` (B158 follow-up D).

Only the pure ``storage_namespace_for`` is unit-testable without the cluster (the lakefs SDK is not in the
light test lane); ``ensure_repo`` itself is validated live against lakeFS. The namespace convention here is
pinned against what the three existing repos actually use (``s3://datasets/<repo>``, verified 2026-09-05).
"""


def test_storage_namespace_matches_the_existing_convention(lakefs_repo):
    assert lakefs_repo.storage_namespace_for("finance") == "s3://datasets/finance"
    assert lakefs_repo.storage_namespace_for("health") == "s3://datasets/health"
    assert lakefs_repo.storage_namespace_for("music") == "s3://datasets/music"


def test_storage_namespace_for_a_new_domain(lakefs_repo):
    # a brand-new domain reuses the shared `datasets` bucket — only the repo path differs
    assert lakefs_repo.storage_namespace_for("climate") == "s3://datasets/climate"
