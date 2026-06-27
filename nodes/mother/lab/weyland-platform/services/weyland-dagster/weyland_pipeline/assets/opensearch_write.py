"""B65 Tier-1 — OpenSearch BM25 index of the corpus (the lexical / sparse retrieval backend).

Indexes each chunk's TEXT (content + metadata) into the `weyland_chunks` OpenSearch index so the
tool-server can do BM25 keyword search — the sparse complement to the 4 dense/vector backends
(pgvector/Qdrant/Weaviate/Neo4j). No vectors stored here; OpenSearch analyzes `content` for BM25.
The standalone instance runs with security DISABLED → plain HTTP, no creds. Mirrors qdrant_write's
delete-then-index + orphan-prune shape (and the same aidlc-kb domain protection).
"""
import json
import os
from collections import defaultdict

import httpx
from dagster import MetadataValue, Output, asset, get_dagster_logger

INDEX = "weyland_chunks"
_OS = os.environ.get("OPENSEARCH_ENDPOINT", "http://opensearch-cluster-master.opensearch.svc.cluster.local:9200")

_MAPPING = {
    "mappings": {
        "properties": {
            "source_path": {"type": "keyword"},
            "source_name": {"type": "keyword"},
            "chunk_index": {"type": "integer"},
            "chunk_title": {"type": "text"},
            "content": {"type": "text"},  # analyzed → BM25
            "domain": {"type": "keyword"},
        }
    }
}


@asset(
    description="Index each changed document's chunks into OpenSearch as text (BM25 lexical backend). "
    "Prunes orphan docs whose source_path is no longer collected."
)
def opensearch_write(source_document: list[dict], hash_check: dict, embeddings: list[dict]) -> Output[dict]:
    log = get_dagster_logger()
    current_paths = {doc["source_path"] for doc in source_document}
    client = httpx.Client(base_url=_OS, timeout=120)
    try:
        if client.head(f"/{INDEX}").status_code == 404:
            client.put(f"/{INDEX}", json=_MAPPING).raise_for_status()

        docs_written = 0
        chunks_written = 0
        if embeddings:
            by_source: dict = defaultdict(list)
            for ch in embeddings:
                by_source[ch["source_path"]].append(ch)
            for sp, chs in by_source.items():
                # remove this source's existing chunks, then re-index (handles a shrunk chunk count)
                client.post(f"/{INDEX}/_delete_by_query", json={"query": {"term": {"source_path": sp}}})
                lines = []
                for ch in chs:
                    lines.append(json.dumps({"index": {"_id": f"{sp}:{ch['chunk_index']}"}}))
                    lines.append(json.dumps({
                        "source_path": sp,
                        "source_name": chs[0]["source_name"],
                        "chunk_index": ch["chunk_index"],
                        "chunk_title": ch["chunk_title"],
                        "content": ch["content"],
                    }))
                client.post(
                    f"/{INDEX}/_bulk", content="\n".join(lines) + "\n",
                    headers={"Content-Type": "application/x-ndjson"},
                ).raise_for_status()
                docs_written += 1
                chunks_written += len(chs)

        # Orphan prune — only when sources were actually collected (empty => bad run, skip to avoid
        # wiping the index); protect the aidlc-kb corpus (domain) like qdrant_write does.
        chunks_pruned = 0
        if current_paths:
            q = {"query": {"bool": {"must_not": [
                {"terms": {"source_path": list(current_paths)}},
                {"term": {"domain": "aidlc-kb"}},
            ]}}}
            r = client.post(f"/{INDEX}/_delete_by_query", json=q)
            chunks_pruned = r.json().get("deleted", 0) if r.status_code == 200 else 0
        else:
            log.warning("[opensearch_write] current_paths empty — skipping orphan prune.")

        skipped = not embeddings and chunks_pruned == 0
        return Output(
            {"documents_written": docs_written, "chunks_written": chunks_written,
             "chunks_pruned": chunks_pruned, "skipped": skipped},
            metadata={
                "documents_written": MetadataValue.int(docs_written),
                "chunks_written": MetadataValue.int(chunks_written),
                "chunks_pruned": MetadataValue.int(chunks_pruned),
            },
        )
    finally:
        client.close()
