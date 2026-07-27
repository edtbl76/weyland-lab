"""B37 Phase 1 — ingest the (brand-neutral) AIDLC knowledge repos from MinIO into all 4 backends.

Separate group ("aidlc_kb") + on-demand job — NOT the 15-min docs cron — because the corpus is static
(re-run only after re-uploading to MinIO). Lands in the SAME stores as the docs pipeline (rag_chunks,
qdrant weyland_chunks, weaviate WeylandChunk, neo4j Document/Chunk) so the same /context/* retrieval finds
it, but under an `aidlc-kb/` source_path namespace so the two corpora coexist.

The catch this design solves: every docs-pipeline write prunes orphans globally (source_path not in its
current set), which would wipe these KB rows every 15 min. Both sides are now scope-guarded — the docs
writes skip `aidlc-kb/` paths (and qdrant's `domain` payload), and this asset only prunes within the KB
namespace. Source files are read straight from the MinIO bucket; index.md/README.md are not chunked (per
the B37 (f) decision — they may feed the Phase-2 frontmatter graph instead).
"""
import hashlib
import json
import os
from collections import defaultdict

from dagster import asset, Output, MetadataValue
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue, MatchAny,
)
from weaviate.classes.config import Configure, Property, DataType, ReferenceProperty
from weaviate.classes.query import Filter as WvFilter

from weyland_pipeline.resources import (
    PostgresResource, SentenceTransformerResource, QdrantResource, WeaviateResource, Neo4jResource,
)
# Reuse the canonical helpers so KB chunking/encoding matches the docs pipeline exactly.
from weyland_pipeline.assets.chunks import _markdown_chunks, embed_text
from weyland_pipeline.assets.pgvector_write import _to_vector
from weyland_pipeline.assets.qdrant_write import _point_id, COLLECTION, DIMS

KB_PREFIX = "aidlc-kb/"
KB_DOMAIN = "aidlc-kb"                       # qdrant payload discriminator (docs points lack it)
_SKIP_NAMES = {"index.md", "README.md"}       # not chunked (navigation / brand)


def _group_by_source(embedded: list[dict]) -> dict:
    grouped: dict = defaultdict(list)
    for chunk in embedded:
        grouped[chunk["source_path"]].append(chunk)
    for sp in grouped:
        grouped[sp].sort(key=lambda c: c["chunk_index"])
    return grouped


def _parse_frontmatter(content: str) -> dict:
    """Minimal, dep-free YAML-frontmatter reader for the fields the graph needs. The KB frontmatter is
    uniform (`key: scalar` or `key: [a, b, c]`), so a full YAML parser isn't required. Returns {} if absent."""
    if not content.startswith("---"):
        return {}
    end = content.find("\n---", 3)
    if end == -1:
        return {}
    fm: dict = {}
    for line in content[3:end].splitlines():
        line = line.strip()
        if not line or ":" not in line or line.startswith("#"):
            continue
        key, _, val = line.partition(":")
        key, val = key.strip(), val.strip()
        if val.startswith("[") and val.endswith("]"):
            fm[key] = [x.strip() for x in val[1:-1].split(",") if x.strip()]
        elif val:
            fm[key] = val
    return fm


def _read_minio_docs(log) -> list[dict]:
    """Pull every chunk-eligible markdown object out of the MinIO bucket as source_document-shaped dicts."""
    from minio import Minio

    endpoint = os.environ.get("MINIO_ENDPOINT", "minio.minio.svc.cluster.local:9000")
    bucket = os.environ.get("AIDLC_KB_BUCKET", "aidlc-kb")
    secure = os.environ.get("MINIO_SECURE", "false").lower() == "true"
    client = Minio(
        endpoint,
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=secure,
    )

    docs: list[dict] = []
    for obj in client.list_objects(bucket, recursive=True):
        key = obj.object_name
        name = key.rsplit("/", 1)[-1]
        if not name.endswith(".md") or name in _SKIP_NAMES:
            continue
        resp = client.get_object(bucket, key)
        try:
            content = resp.read().decode("utf-8")
        finally:
            resp.close()
            resp.release_conn()
        if not content.strip():
            continue
        docs.append({
            "content": content,
            "source_path": f"{KB_PREFIX}{key}",
            "source_name": name,
            "kind": "markdown",
            "fm": _parse_frontmatter(content),
        })
    log.info("aidlc_kb: read %d markdown docs from MinIO bucket '%s'", len(docs), bucket)
    return docs


# --- per-backend writers (mirror the docs assets; prune scoped to the aidlc-kb/ namespace) --------------

def _write_pgvector(grouped, current_paths, gate, meta_by_path, postgres: PostgresResource) -> dict:
    docs_written = chunks_written = pruned = 0
    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            for sp, doc_chunks in grouped.items():
                meta = meta_by_path[sp]
                cur.execute(
                    """
                    INSERT INTO rag_documents (name, source_type, source_path, content_hash, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (source_path) DO UPDATE SET
                        name = EXCLUDED.name, source_type = EXCLUDED.source_type,
                        content_hash = EXCLUDED.content_hash, updated_at = now()
                    RETURNING id
                    """,
                    (meta["source_name"], "markdown", sp, gate[sp]["incoming_hash"],
                     json.dumps({"domain": KB_DOMAIN})),
                )
                document_id = cur.fetchone()[0]
                cur.execute("DELETE FROM rag_chunks WHERE document_id = %s", (document_id,))
                for chunk in doc_chunks:
                    metadata = {"title": chunk["chunk_title"]} if chunk["chunk_title"] else {}
                    cur.execute(
                        "INSERT INTO rag_chunks (document_id, chunk_index, content, embedding, metadata) "
                        "VALUES (%s, %s, %s, %s::vector, %s)",
                        (document_id, chunk["chunk_index"], chunk["content"],
                         _to_vector(chunk["embedding"]), json.dumps(metadata)),
                    )
                docs_written += 1
                chunks_written += len(doc_chunks)

            if current_paths:  # KB-scoped prune (rag_chunks cascade via document_id FK)
                cur.execute(
                    "DELETE FROM rag_documents WHERE source_path LIKE %s AND source_path <> ALL(%s)",
                    (KB_PREFIX + "%", list(current_paths)),
                )
                pruned = cur.rowcount
    return {"documents_written": docs_written, "chunks_written": chunks_written, "documents_pruned": pruned}


def _write_qdrant(grouped, current_paths, qdrant: QdrantResource) -> dict:
    client = qdrant.get_client()
    if not client.collection_exists(COLLECTION):
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=DIMS, distance=Distance.COSINE),
        )
    docs_written = points_written = pruned = 0
    for sp, doc_chunks in grouped.items():
        source_name = doc_chunks[0]["source_name"]
        client.delete(
            collection_name=COLLECTION,
            points_selector=Filter(must=[FieldCondition(key="source_path", match=MatchValue(value=sp))]),
        )
        client.upsert(collection_name=COLLECTION, points=[
            PointStruct(
                id=_point_id(sp, c["chunk_index"]),
                vector=c["embedding"],
                payload={
                    "source_path": sp, "source_name": source_name, "chunk_index": c["chunk_index"],
                    "chunk_title": c["chunk_title"], "content": c["content"], "domain": KB_DOMAIN,
                },
            ) for c in doc_chunks
        ])
        docs_written += 1
        points_written += len(doc_chunks)

    if current_paths:  # KB-scoped prune: KB-domain points whose source_path is no longer present
        orphan = Filter(
            must=[FieldCondition(key="domain", match=MatchValue(value=KB_DOMAIN))],
            must_not=[FieldCondition(key="source_path", match=MatchAny(any=list(current_paths)))],
        )
        pruned = client.count(collection_name=COLLECTION, count_filter=orphan, exact=True).count
        if pruned:
            client.delete(collection_name=COLLECTION, points_selector=orphan)
    return {"documents_written": docs_written, "points_written": points_written, "points_pruned": pruned}


def _wv_stored_kb_paths(collection) -> set:
    paths = set()
    for obj in collection.iterator(return_properties=["source_path"]):
        sp = obj.properties.get("source_path")
        if sp and sp.startswith(KB_PREFIX):
            paths.add(sp)
    return paths


def _write_weaviate(grouped, current_paths, weaviate: WeaviateResource) -> dict:
    client = weaviate.get_client()
    try:
        # WeylandDocument / WeylandChunk are bootstrapped by the docs pipeline; create defensively if absent.
        existing = {c.name for c in client.collections.list_all().values()}
        if "WeylandDocument" not in existing or "WeylandChunk" not in existing:
            if "WeylandDocument" not in existing:
                client.collections.create(
                    name="WeylandDocument", vectorizer_config=Configure.Vectorizer.none(),
                    properties=[Property(name="source_path", data_type=DataType.TEXT),
                                Property(name="source_name", data_type=DataType.TEXT),
                                Property(name="name", data_type=DataType.TEXT)],
                )
            if "WeylandChunk" not in existing:
                client.collections.create(
                    name="WeylandChunk", vectorizer_config=Configure.Vectorizer.none(),
                    properties=[Property(name="source_path", data_type=DataType.TEXT),
                                Property(name="chunk_index", data_type=DataType.INT),
                                Property(name="chunk_title", data_type=DataType.TEXT),
                                Property(name="content", data_type=DataType.TEXT)],
                    references=[ReferenceProperty(name="hasDocument", target_collection="WeylandDocument"),
                                ReferenceProperty(name="previousChunk", target_collection="WeylandChunk"),
                                ReferenceProperty(name="nextChunk", target_collection="WeylandChunk")],
                )

        chunks_col = client.collections.get("WeylandChunk")
        docs_col = client.collections.get("WeylandDocument")
        docs_written = objects_written = pruned = 0

        for sp, doc_chunks in grouped.items():
            source_name = doc_chunks[0]["source_name"]
            chunks_col.data.delete_many(where=WvFilter.by_property("source_path").equal(sp))
            docs_col.data.delete_many(where=WvFilter.by_property("source_path").equal(sp))
            doc_uuid = docs_col.data.insert(
                properties={"source_path": sp, "source_name": source_name, "name": source_name})
            chunk_uuids = []
            for c in doc_chunks:
                cu = chunks_col.data.insert(
                    properties={"source_path": sp, "chunk_index": c["chunk_index"],
                                "chunk_title": c["chunk_title"] or "", "content": c["content"]},
                    vector=c["embedding"], references={"hasDocument": doc_uuid})
                chunk_uuids.append(cu)
            for i, cu in enumerate(chunk_uuids):
                if i > 0:
                    chunks_col.data.reference_add(from_uuid=cu, from_property="previousChunk", to=chunk_uuids[i - 1])
                if i < len(chunk_uuids) - 1:
                    chunks_col.data.reference_add(from_uuid=cu, from_property="nextChunk", to=chunk_uuids[i + 1])
            docs_written += 1
            objects_written += len(chunk_uuids) + 1

        if current_paths:  # KB-scoped prune
            orphans = _wv_stored_kb_paths(chunks_col) | _wv_stored_kb_paths(docs_col)
            for orphan in (orphans - current_paths):
                cr = chunks_col.data.delete_many(where=WvFilter.by_property("source_path").equal(orphan))
                dr = docs_col.data.delete_many(where=WvFilter.by_property("source_path").equal(orphan))
                pruned += getattr(cr, "successful", 0) + getattr(dr, "successful", 0)
        return {"documents_written": docs_written, "objects_written": objects_written, "objects_pruned": pruned}
    finally:
        client.close()


def _write_neo4j(grouped, current_paths, neo4j: Neo4jResource) -> dict:
    driver = neo4j.get_driver()
    docs_written = nodes_written = rels_written = pruned = 0
    try:
        with driver.session() as session:
            for sp, doc_chunks in grouped.items():
                source_name = doc_chunks[0]["source_name"]
                with session.begin_transaction() as tx:
                    tx.run("MATCH (c:Chunk {source_path: $sp}) DETACH DELETE c", sp=sp)
                    tx.run("MATCH (d:Document {source_path: $sp}) DETACH DELETE d", sp=sp)
                    tx.run("CREATE (d:Document {source_path: $sp, source_name: $sn, name: $name, "
                           "domain: $dom, ingested_at: datetime()})",
                           sp=sp, sn=source_name, name=source_name, dom=KB_DOMAIN)
                    for c in doc_chunks:
                        tx.run("CREATE (c:Chunk {source_path: $sp, chunk_index: $idx, chunk_title: $title, "
                               "content: $content, embedding: $embedding, domain: $dom})",
                               sp=sp, idx=c["chunk_index"], title=c["chunk_title"] or "",
                               content=c["content"], embedding=c["embedding"], dom=KB_DOMAIN)
                    tx.run("MATCH (d:Document {source_path: $sp}), (c:Chunk {source_path: $sp}) "
                           "CREATE (c)-[:BELONGS_TO]->(d)", sp=sp)
                    tx.run("MATCH (c1:Chunk {source_path: $sp}), (c2:Chunk {source_path: $sp}) "
                           "WHERE c2.chunk_index = c1.chunk_index + 1 CREATE (c1)-[:NEXT]->(c2)", sp=sp)
                    tx.commit()
                n = len(doc_chunks)
                docs_written += 1
                nodes_written += 1 + n
                rels_written += n + max(0, n - 1)

            if current_paths:  # KB-scoped prune
                res = session.run(
                    "MATCH (n) WHERE (n:Document OR n:Chunk) AND n.source_path STARTS WITH $prefix "
                    "AND NOT n.source_path IN $current DETACH DELETE n RETURN count(n) AS pruned",
                    prefix=KB_PREFIX, current=list(current_paths))
                pruned = res.single()["pruned"]
        return {"documents_written": docs_written, "nodes_written": nodes_written,
                "relationships_written": rels_written, "nodes_pruned": pruned}
    finally:
        driver.close()


def _kb_graph_present(neo4j: Neo4jResource) -> bool:
    """True if the frontmatter graph already exists (any :Entry node in the KB domain)."""
    driver = neo4j.get_driver()
    try:
        with driver.session() as session:
            return session.run(
                "MATCH (e:Entry {domain: $d}) RETURN count(e) AS c", d=KB_DOMAIN
            ).single()["c"] > 0
    finally:
        driver.close()


def _write_neo4j_graph(docs, neo4j: Neo4jResource) -> dict:
    """B37 Phase 2 — deterministic frontmatter graph over the KB Document nodes (created in Phase 1).
    Promotes each entry's Document to also carry the :Entry label + entry_id, then rebuilds the
    relationship layer from declared frontmatter: RELATED_TO (entry->entry), SURFACES_AT (->Stage),
    TAGGED (->Tag), IN_VERTICAL (->Vertical). No LLM — links are author-declared. Idempotent: KB edges
    are cleared and rebuilt each run so removed refs don't linger; Stage/Tag/Vertical nodes are MERGEd.
    """
    entries = [d for d in docs if d.get("fm", {}).get("id")]
    driver = neo4j.get_driver()
    stats = {"entries": len(entries), "related": 0, "surfaces_at": 0, "tagged": 0, "vertical": 0}
    try:
        with driver.session() as session:
            # Clear existing KB frontmatter edges (version-safe: one rel type per statement).
            for rel in ("RELATED_TO", "SURFACES_AT", "TAGGED", "IN_VERTICAL"):
                session.run(
                    f"MATCH (e:Document {{domain: $dom}})-[r:{rel}]->() DELETE r", dom=KB_DOMAIN)

            # Pass 1: label + scalar props (so RELATED_TO targets all exist before pass 2).
            for d in entries:
                fm = d["fm"]
                session.run(
                    "MATCH (e:Document {source_path: $sp}) "
                    "SET e:Entry, e.entry_id = $id, e.complexity = $cx, e.vertical = $vt",
                    sp=d["source_path"], id=fm["id"], cx=fm.get("complexity"), vt=fm.get("vertical"))

            # Pass 2: relationships from declared frontmatter.
            for d in entries:
                fm, eid = d["fm"], d["fm"]["id"]
                if fm.get("surfaces-at"):
                    session.run(
                        "MATCH (e:Entry {entry_id: $id}) UNWIND $xs AS st "
                        "MERGE (s:Stage {name: st}) MERGE (e)-[:SURFACES_AT]->(s)",
                        id=eid, xs=fm["surfaces-at"])
                    stats["surfaces_at"] += len(fm["surfaces-at"])
                if fm.get("tags"):
                    session.run(
                        "MATCH (e:Entry {entry_id: $id}) UNWIND $xs AS tg "
                        "MERGE (t:Tag {name: tg}) MERGE (e)-[:TAGGED]->(t)",
                        id=eid, xs=fm["tags"])
                    stats["tagged"] += len(fm["tags"])
                if fm.get("vertical"):
                    session.run(
                        "MATCH (e:Entry {entry_id: $id}) "
                        "MERGE (v:Vertical {name: $vt}) MERGE (e)-[:IN_VERTICAL]->(v)",
                        id=eid, vt=fm["vertical"])
                    stats["vertical"] += 1
                if fm.get("related"):
                    # MATCH on target => dangling refs (no such entry_id) simply create no edge.
                    res = session.run(
                        "MATCH (a:Entry {entry_id: $id}) UNWIND $rs AS rid "
                        "MATCH (b:Entry {entry_id: rid}) MERGE (a)-[:RELATED_TO]->(b) "
                        "RETURN count(*) AS c", id=eid, rs=fm["related"])
                    stats["related"] += res.single()["c"]
    finally:
        driver.close()
    return stats


@asset(
    group_name="aidlc_kb",
    description="Ingest the brand-neutral AIDLC knowledge repos from MinIO into all 4 backends "
                "(H2-chunk -> bge embed -> pgvector/qdrant/weaviate/neo4j), KB-scoped hash-gate + prune, "
                "plus a deterministic frontmatter graph in Neo4j (RELATED_TO/SURFACES_AT/TAGGED/IN_VERTICAL).",
)
def aidlc_kb_ingest(
    context,
    postgres: PostgresResource,
    sentence_transformer: SentenceTransformerResource,
    qdrant: QdrantResource,
    weaviate: WeaviateResource,
    neo4j: Neo4jResource,
) -> Output[dict]:
    log = context.log
    docs = _read_minio_docs(log)
    current_paths = {d["source_path"] for d in docs}
    meta_by_path = {d["source_path"]: d for d in docs}

    if not current_paths:
        # Empty read = likely a MinIO/auth failure. Do NOT prune (would wipe the KB) — bail loudly.
        log.warning("aidlc_kb: 0 docs read from MinIO — skipping writes AND prune to protect existing rows.")
        return Output({"skipped": True, "reason": "empty MinIO read"},
                      metadata={"docs_read": 0, "skipped": MetadataValue.bool(True)})

    # Hash-gate against rag_documents (same source of truth as the docs pipeline).
    gate: dict = {}
    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            for d in docs:
                h = hashlib.sha256(d["content"].encode("utf-8")).hexdigest()
                cur.execute("SELECT content_hash FROM rag_documents WHERE source_path = %s", (d["source_path"],))
                row = cur.fetchone()
                gate[d["source_path"]] = {"changed": row is None or row[0] != h, "incoming_hash": h}

    changed = [d for d in docs if gate[d["source_path"]]["changed"]]
    chunk_list: list[dict] = []
    for d in changed:
        for ch in _markdown_chunks(d["content"]):
            ch["source_path"] = d["source_path"]
            ch["source_name"] = d["source_name"]
            ch["kind"] = "markdown"
            chunk_list.append(ch)
    log.info("aidlc_kb: encoding %d chunks (batched)…", len(chunk_list))  # B105: progress marker
    _vecs = sentence_transformer.encode_batch([embed_text(c) for c in chunk_list])  # B74 topic-prefix + B105 batch
    embedded = [{**c, "embedding": v} for c, v in zip(chunk_list, _vecs)]
    grouped = _group_by_source(embedded)
    log.info("aidlc_kb: %d/%d docs changed -> %d chunks to embed/write", len(changed), len(docs), len(embedded))

    pg = _write_pgvector(grouped, current_paths, gate, meta_by_path, postgres)
    qd = _write_qdrant(grouped, current_paths, qdrant)
    wv = _write_weaviate(grouped, current_paths, weaviate)
    n4 = _write_neo4j(grouped, current_paths, neo4j)

    # Phase 2 (B37 step 5): rebuild the frontmatter graph over ALL current entries. Run it when content
    # changed OR when the graph doesn't exist yet (e.g. first run after Phase 1 already ingested chunks,
    # where nothing is "changed" but no :Entry graph exists). A true no-op run with a present graph skips it.
    build_graph = bool(changed) or not _kb_graph_present(neo4j)
    graph = _write_neo4j_graph(docs, neo4j) if build_graph else {"skipped": "no changes, graph present"}

    summary = {
        "docs_read": len(docs), "docs_changed": len(changed), "chunks": len(embedded),
        "pgvector": pg, "qdrant": qd, "weaviate": wv, "neo4j": n4, "graph": graph,
    }
    log.info("aidlc_kb summary: %s", summary)
    return Output(summary, metadata={
        "docs_read": MetadataValue.int(len(docs)),
        "docs_changed": MetadataValue.int(len(changed)),
        "chunks": MetadataValue.int(len(embedded)),
        "pgvector_chunks": MetadataValue.int(pg["chunks_written"]),
        "graph": MetadataValue.json(graph),
        "pruned": MetadataValue.json({
            "pgvector": pg["documents_pruned"], "qdrant": qd["points_pruned"],
            "weaviate": wv["objects_pruned"], "neo4j": n4["nodes_pruned"],
        }),
    })


@asset(
    group_name="aidlc_kb",
    description="Load the AIDLC knowledge corpus into MongoDB (db aidlc_kb, collection entries) — one doc per "
                "markdown file with its frontmatter flattened to top-level queryable fields + the body. Enables "
                "scanning the methodology BY FRONTMATTER (type/stage/vertical/…) — the structured-lookup the "
                "vector RAG (semantic) and Neo4j (relationships) don't serve. Drop + reload (idempotent).",
)
def aidlc_kb_mongo(context) -> Output[dict]:
    from .datasets_lib.loaders import _mongo_client

    log = context.log
    docs = _read_minio_docs(log)
    if not docs:
        # Empty read = likely MinIO/auth failure — don't drop the collection.
        log.warning("aidlc_kb_mongo: 0 docs read from MinIO — skipping (protecting existing collection).")
        return Output({"skipped": True}, metadata={"docs": 0, "skipped": MetadataValue.bool(True)})
    mongo_docs = [
        {**d["fm"], "name": d["source_name"], "path": d["source_path"], "kind": d["kind"], "content": d["content"]}
        for d in docs
    ]
    client = _mongo_client()
    try:
        coll = client["aidlc_kb"]["entries"]
        coll.drop()
        coll.insert_many(mongo_docs, ordered=False)
    finally:
        client.close()
    log.info("aidlc_kb_mongo: wrote %d docs to aidlc_kb.entries", len(mongo_docs))
    return Output({"docs": len(mongo_docs)}, metadata={"docs": MetadataValue.int(len(mongo_docs))})
