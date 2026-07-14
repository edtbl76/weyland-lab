"""OpenSearch handler — BM25 lexical index `weyland_chunks` (mirrors the retired opensearch_write asset).
No vectors: OpenSearch analyzes `content` for BM25. Standalone instance runs security-disabled → plain HTTP,
no creds. Idempotent: upsert = index by deterministic _id `{source_path}:{chunk_index}`; delete = delete-by-query
on source_path (the streaming form of the asset's per-doc clear + orphan prune). aidlc-kb (its own domain, own
source_paths) is never matched by a docs delete."""
import hashlib
import os

import httpx

INDEX = "weyland_chunks"


def _doc_id(source_path: str, chunk_index: int) -> str:
    # Deterministic + slash-free: source_path has '/', which would break the _doc URL path (400).
    return hashlib.md5(f"{source_path}:{chunk_index}".encode()).hexdigest()
_MAPPING = {
    "mappings": {
        "properties": {
            "source_path": {"type": "keyword"},
            "source_name": {"type": "keyword"},
            "chunk_index": {"type": "integer"},
            "chunk_title": {"type": "text"},
            "content": {"type": "text"},
            "domain": {"type": "keyword"},
        }
    }
}


class OpensearchHandler:
    def __init__(self):
        url = os.environ.get("OPENSEARCH_URL", "http://opensearch-cluster-master.opensearch.svc.cluster.local:9200")
        self.client = httpx.Client(base_url=url, timeout=120)

    def ensure(self):
        if self.client.head(f"/{INDEX}").status_code == 404:
            self.client.put(f"/{INDEX}", json=_MAPPING).raise_for_status()

    def on_delete(self, source_path: str):
        self.client.post(f"/{INDEX}/_delete_by_query",
                         json={"query": {"term": {"source_path": source_path}}}).raise_for_status()

    def on_upsert(self, rec: dict):
        self.client.put(
            f"/{INDEX}/_doc/{_doc_id(rec['source_path'], rec['chunk_index'])}",
            json={
                "source_path": rec["source_path"],
                "source_name": rec.get("source_name"),
                "chunk_index": rec["chunk_index"],
                "chunk_title": rec.get("chunk_title"),
                "content": rec.get("chunk_text"),
            },
        ).raise_for_status()
