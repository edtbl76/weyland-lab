import hashlib
from dagster import asset


@asset(description="Compute SHA256 hash of each source file's content, keyed by source_path.")
def content_hash(source_document: list[dict]) -> dict:
    # Returns {source_path: sha256_hex} for every collected file.
    return {
        doc["source_path"]: hashlib.sha256(
            doc["content"].encode("utf-8")
        ).hexdigest()
        for doc in source_document
    }
