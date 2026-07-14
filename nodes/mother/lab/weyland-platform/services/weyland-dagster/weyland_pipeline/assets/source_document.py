import os
import shutil
import subprocess
import tempfile
from pathlib import PurePosixPath
from dagster import asset, RetryPolicy, get_dagster_logger

# Files matched by extension anywhere under nodes/ (and docs/ markdown is handled separately).
_CODE_EXTENSIONS = {
    ".md", ".py", ".yaml", ".yml", ".sql", ".cypher", ".sh",
    ".service", ".template",
}
# Exact basenames (no extension) that are always treated as code.
_CODE_BASENAMES = {"Dockerfile"}

# Substring / suffix patterns that EXCLUDE a path regardless of where it matches.
_EXCLUDE_SUFFIXES = (".key", ".pem", ".env", ".lock", ".png", ".jpg", ".pdf")
_EXCLUDE_SUBSTRINGS = ("encryption-key", "secret")

# Directory components anywhere in the path that exclude it.
_EXCLUDE_DIR_COMPONENTS = {"node_modules", "__pycache__", ".git"}
# Path prefixes (repo-relative, posix) that exclude the whole subtree.
_EXCLUDE_PREFIXES = ("nodes/openclaw/lab/",)


def _is_excluded(rel_posix: str) -> bool:
    lower = rel_posix.lower()
    if any(lower.endswith(suffix) for suffix in _EXCLUDE_SUFFIXES):
        return True
    if any(sub in lower for sub in _EXCLUDE_SUBSTRINGS):
        return True
    parts = set(PurePosixPath(rel_posix).parts)
    if parts & _EXCLUDE_DIR_COMPONENTS:
        return True
    if any(rel_posix.startswith(prefix) for prefix in _EXCLUDE_PREFIXES):
        return True
    return False


def _has_shebang(abs_path: str) -> bool:
    try:
        with open(abs_path, "rb") as f:
            return f.read(2) == b"#!"
    except OSError:
        return False


def _included_kind(rel_posix: str, abs_path: str) -> str | None:
    """Return 'markdown' | 'code' if the file should be ingested, else None."""
    p = PurePosixPath(rel_posix)
    name = p.name
    suffix = p.suffix

    # docs/**/*.md -> markdown
    if rel_posix.startswith("docs/") and suffix == ".md":
        return "markdown"

    # Everything else must be under nodes/
    if not rel_posix.startswith("nodes/"):
        return None

    if suffix == ".md":
        return "markdown"
    if suffix in _CODE_EXTENSIONS:
        return "code"
    if name in _CODE_BASENAMES:
        return "code"
    # Extensionless files inside any bin/ dir with a #! shebang.
    if suffix == "" and "bin" in p.parts[:-1] and _has_shebang(abs_path):
        return "code"
    return None


def collect_source_documents() -> list[dict]:
    log = get_dagster_logger()
    repo_url = os.environ["GIT_REPO_URL"]            # e.g. https://github.com/<org>/weyland.git
    git_ref = os.environ.get("GIT_REF", "").strip()  # branch/tag; empty -> default branch
    token = os.environ.get("GIT_TOKEN", "").strip()  # HTTPS PAT (optional for public repos)

    # Inject the token into the HTTPS URL: https://<token>@github.com/...
    clone_url = repo_url
    if token and repo_url.startswith("https://"):
        clone_url = "https://" + token + "@" + repo_url[len("https://"):]

    tmp_dir = tempfile.mkdtemp(prefix="weyland-clone-")
    try:
        cmd = ["git", "clone", "--depth", "1"]
        if git_ref:
            cmd += ["--branch", git_ref]
        cmd += [clone_url, tmp_dir]
        # Never echo the token-bearing URL into logs.
        log.info("Cloning repo (ref=%s) into %s", git_ref or "<default>", tmp_dir)
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            # Scrub the token from any error output before raising.
            stderr = result.stderr.replace(token, "***") if token else result.stderr
            raise RuntimeError(f"git clone failed (rc={result.returncode}): {stderr}")

        documents: list[dict] = []
        repo_root = os.path.abspath(tmp_dir)
        for dirpath, dirnames, filenames in os.walk(repo_root):
            # Prune excluded directories in-place for efficiency.
            dirnames[:] = [
                d for d in dirnames
                if d not in _EXCLUDE_DIR_COMPONENTS and d != ".git"
            ]
            for filename in filenames:
                abs_path = os.path.join(dirpath, filename)
                rel = os.path.relpath(abs_path, repo_root)
                rel_posix = PurePosixPath(*rel.split(os.sep)).as_posix()

                if _is_excluded(rel_posix):
                    continue
                kind = _included_kind(rel_posix, abs_path)
                if kind is None:
                    continue

                try:
                    with open(abs_path, "r", encoding="utf-8") as f:
                        content = f.read()
                except (OSError, UnicodeDecodeError) as exc:
                    log.warning("Skipping unreadable file %s: %s", rel_posix, exc)
                    continue

                if not content.strip():
                    continue

                documents.append({
                    "content": content,
                    "source_path": rel_posix,
                    "source_name": PurePosixPath(rel_posix).name,
                    "kind": kind,
                })

        log.info("Collected %d source files from repo.", len(documents))
        return documents
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@asset(
    retry_policy=RetryPolicy(max_retries=2, delay=30),
    description="Shallow-clone the weyland repo from GitHub and collect docs/ + nodes/ source files.",
)
def source_document() -> list[dict]:
    """Asset wrapper. The reusable collector is collect_source_documents() so rag_stream_produce can call it
    directly — no fs-IO-manager cross-run input load, which fails when the producer is materialized alone."""
    return collect_source_documents()
