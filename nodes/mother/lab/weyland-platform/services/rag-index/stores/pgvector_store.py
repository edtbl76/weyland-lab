"""pgvector handler — owns the docs rows of rag_documents + rag_chunks (mirrors the retired pgvector_write
asset). This consumer OWNS these tables for the docs corpus; the producer's change-detection lives separately in
rag_manifest (design §3.2b), so there is no write race. Idempotent: rag_documents upsert on source_path,
rag_chunks upsert on (document_id, chunk_index) — a unique index we ensure at startup. delete removes the doc +
its chunks. Postgres is strict mTLS, so this consumer is meshed (sidecar on, kafka ports excluded)."""
import json
import os

import psycopg2


class PgvectorHandler:
    def __init__(self):
        self.conn = psycopg2.connect(
            host=os.environ.get("WEYLAND_PG_HOST", "weyland-postgres.weyland.svc.cluster.local"),
            port=int(os.environ.get("WEYLAND_PG_PORT", "5432")),
            dbname=os.environ.get("WEYLAND_PG_DB", "weyland"),
            user=os.environ.get("WEYLAND_PG_USER", "weyland"),
            password=os.environ["WEYLAND_PG_PASSWORD"],
        )
        self.conn.autocommit = True

    def ensure(self):
        with self.conn.cursor() as cur:
            # enables the rag_chunks ON CONFLICT upsert (the old asset relied on delete-then-insert instead)
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS rag_chunks_doc_chunk_uq "
                        "ON rag_chunks (document_id, chunk_index)")

    def on_delete(self, source_path: str):
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM rag_chunks WHERE document_id IN "
                        "(SELECT id FROM rag_documents WHERE source_path = %s)", (source_path,))
            cur.execute("DELETE FROM rag_documents WHERE source_path = %s", (source_path,))

    def on_upsert(self, rec: dict):
        vec = "[" + ",".join(str(v) for v in rec["vector"]) + "]"
        meta = {"title": rec["chunk_title"]} if rec.get("chunk_title") else {}
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO rag_documents (name, source_type, source_path, content_hash, metadata)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (source_path) DO UPDATE SET
                    name = EXCLUDED.name, source_type = EXCLUDED.source_type,
                    content_hash = EXCLUDED.content_hash, updated_at = now()
                RETURNING id
                """,
                (rec.get("source_name"), rec.get("kind"), rec["source_path"], rec.get("content_hash"),
                 json.dumps({})),
            )
            document_id = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO rag_chunks (document_id, chunk_index, content, embedding, metadata)
                VALUES (%s, %s, %s, %s::vector, %s)
                ON CONFLICT (document_id, chunk_index) DO UPDATE SET
                    content = EXCLUDED.content, embedding = EXCLUDED.embedding, metadata = EXCLUDED.metadata
                """,
                (document_id, rec["chunk_index"], rec.get("chunk_text"), vec, json.dumps(meta)),
            )
