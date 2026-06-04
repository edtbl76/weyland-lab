import hashlib
from dagster import asset


@asset(description="Compute SHA256 hash of the source document content.")
def content_hash(source_document: dict) -> dict:
    digest = hashlib.sha256(source_document["content"].encode("utf-8")).hexdigest()
    return {"hash": digest}
