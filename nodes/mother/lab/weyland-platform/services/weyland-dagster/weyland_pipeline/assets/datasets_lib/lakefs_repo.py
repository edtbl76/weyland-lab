"""ensure_repo — idempotent lakeFS repo bootstrap (B158 follow-up D).

The B158 audit found the one place the "storage is invisible" claim breaks for a product author: NOTHING
in the paved path creates the lakeFS repo. Every land + commit asset assumes ``lakefs.Repository(cfg.repo)``
already exists, so onboarding a new domain silently required an operator to pre-create the repo out of
band — and a write to a missing repo fails only at runtime, the exact silent-failure class the lab's
corrections warn about. ``build_land_asset`` now calls ``ensure_repo`` before the first write, so a new
domain's repo self-provisions on first land.

The lakeFS storage backend bucket (``s3://datasets``) is SHARED across every domain (finance/health/music
all live under it) and already exists — only the per-domain lakeFS repo is created here, mapped to
``s3://datasets/<repo>``, the convention every existing repo follows (verified live 2026-09-05).

Module scope is import-clean (stdlib only) so ``storage_namespace_for`` tests in isolation like the other
leaves; the lakefs SDK and the ``io`` helpers are imported lazily inside ``ensure_repo`` (runtime only).
"""
import os

_STORAGE_BUCKET = "datasets"  # the shared lakeFS storage backend bucket: s3://datasets/<repo>


def storage_namespace_for(repo):
    """The lakeFS storage namespace for a domain repo — ``s3://datasets/<repo>``, the convention every
    existing repo follows."""
    return f"s3://{_STORAGE_BUCKET}/{repo}"


def ensure_repo(repo, *, client=None, branch=None):
    """Create the lakeFS repo if it is missing, idempotently. Safe to call on every land run:
    ``create(..., exist_ok=True)`` is a no-op when the repo already exists. Returns the
    ``lakefs.Repository`` handle. Raises loudly (fail closed) if creation genuinely fails — a land that
    cannot ensure its repo must not proceed to write into a repo that does not exist."""
    import lakefs

    from . import io  # lazy: runtime-only, keeps module scope import-clean for isolation tests

    lc = client or lakefs.Client(
        host=io.endpoint(),
        username=os.environ["LAKEFS_ACCESS_KEY_ID"],
        password=os.environ["LAKEFS_SECRET_ACCESS_KEY"],
    )
    repo_obj = lakefs.Repository(repo, client=lc)
    try:
        repo_obj.create(
            storage_namespace=storage_namespace_for(repo),
            default_branch=branch or io.branch(),
            exist_ok=True,
        )
    except Exception as e:  # noqa: BLE001 — re-raised: a repo we could not ensure must fail the land loudly
        raise RuntimeError(f"ensure_repo({repo!r}) failed: {e}") from e
    return repo_obj
