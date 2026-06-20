import mimetypes
import os
import shutil
import subprocess
import tempfile

from dagster import asset, RetryPolicy, get_dagster_logger

# TechDocs static-site sync (B41). The IDP serves TechDocs with `builder: external`, so a docs/ change is
# invisible in the portal until the site is rebuilt and re-published to MinIO. This asset closes that gap:
# shallow-clone the repo, run `mkdocs build` (the techdocs-core plugin emits techdocs_metadata.json as part
# of the build), and upload the resulting site to the `techdocs` bucket under the entity path Backstage's
# awsS3 publisher reads. Pure Python — no @techdocs/cli, no node in the Dagster image. Reuses the existing
# git-clone (source_document) and MinIO (aidlc_kb) patterns; the pod already has GIT_* and MINIO_* env.

# Backstage's awsS3 publisher stores/serves objects under <namespace>/<kind>/<name>, lowercased. The docs
# entity is `weyland-docs`, a Component in the default namespace.
_ENTITY_PREFIX = "default/component/weyland-docs"


def _clone_repo(log) -> str:
    """Shallow-clone the weyland repo into a temp dir; mirrors source_document's token handling."""
    repo_url = os.environ["GIT_REPO_URL"]
    git_ref = os.environ.get("GIT_REF", "").strip()
    token = os.environ.get("GIT_TOKEN", "").strip()

    clone_url = repo_url
    if token and repo_url.startswith("https://"):
        clone_url = "https://" + token + "@" + repo_url[len("https://"):]

    tmp_dir = tempfile.mkdtemp(prefix="weyland-techdocs-")
    cmd = ["git", "clone", "--depth", "1"]
    if git_ref:
        cmd += ["--branch", git_ref]
    cmd += [clone_url, tmp_dir]
    log.info("Cloning repo (ref=%s) for TechDocs build", git_ref or "<default>")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if result.returncode != 0:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        stderr = result.stderr.replace(token, "***") if token else result.stderr
        raise RuntimeError(f"git clone failed (rc={result.returncode}): {stderr}")
    return tmp_dir


@asset(
    group_name="techdocs",
    retry_policy=RetryPolicy(max_retries=2, delay=30),
    description="Build the repo's mkdocs site and publish it to the MinIO 'techdocs' bucket for the IDP.",
)
def techdocs_publish() -> dict:
    from minio import Minio

    log = get_dagster_logger()
    repo_dir = _clone_repo(log)
    site_dir = tempfile.mkdtemp(prefix="weyland-techdocs-site-")
    try:
        mkdocs_yml = os.path.join(repo_dir, "mkdocs.yml")
        if not os.path.exists(mkdocs_yml):
            raise RuntimeError("mkdocs.yml not found at repo root — cannot build TechDocs")

        # `mkdocs build` with the techdocs-core plugin (declared in mkdocs.yml) produces the TechDocs site
        # AND writes techdocs_metadata.json into the site root — exactly what `@techdocs/cli generate` does.
        build = subprocess.run(
            ["python", "-m", "mkdocs", "build", "-f", mkdocs_yml, "-d", site_dir],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
        )
        if build.returncode != 0:
            raise RuntimeError(f"mkdocs build failed (rc={build.returncode}): {build.stderr}")

        endpoint = os.environ.get("MINIO_ENDPOINT", "minio.minio.svc.cluster.local:9000")
        bucket = os.environ.get("TECHDOCS_BUCKET", "techdocs")
        secure = os.environ.get("MINIO_SECURE", "false").lower() == "true"
        client = Minio(
            endpoint,
            access_key=os.environ["MINIO_ACCESS_KEY"],
            secret_key=os.environ["MINIO_SECRET_KEY"],
            secure=secure,
        )
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)

        uploaded = 0
        for dirpath, _dirnames, filenames in os.walk(site_dir):
            for filename in filenames:
                abs_path = os.path.join(dirpath, filename)
                rel = os.path.relpath(abs_path, site_dir).replace(os.sep, "/")
                key = f"{_ENTITY_PREFIX}/{rel}"
                content_type = mimetypes.guess_type(abs_path)[0] or "application/octet-stream"
                client.fput_object(bucket, key, abs_path, content_type=content_type)
                uploaded += 1

        log.info("techdocs: published %d objects to bucket '%s' under %s/", uploaded, bucket, _ENTITY_PREFIX)
        return {"objects": uploaded, "bucket": bucket, "prefix": _ENTITY_PREFIX}
    finally:
        shutil.rmtree(repo_dir, ignore_errors=True)
        shutil.rmtree(site_dir, ignore_errors=True)
