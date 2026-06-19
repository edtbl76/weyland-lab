from collections import defaultdict
from dagster import asset, Output, MetadataValue
from weyland_pipeline.resources import Neo4jResource


def _group_by_source(embeddings: list[dict]) -> dict:
    grouped: dict = defaultdict(list)
    for chunk in embeddings:
        grouped[chunk["source_path"]].append(chunk)
    for source_path in grouped:
        grouped[source_path].sort(key=lambda c: c["chunk_index"])
    return grouped


@asset(description="Write Document+Chunk nodes and relationships to Neo4j for each changed document. Prunes orphan nodes whose source_path is no longer collected.")
def neo4j_write(
    source_document: list[dict],
    hash_check: dict,
    embeddings: list[dict],
    neo4j: Neo4jResource,
) -> Output[dict]:
    current_paths = {doc["source_path"] for doc in source_document}

    grouped = _group_by_source(embeddings)
    driver = neo4j.get_driver()

    documents_written = 0
    nodes_written = 0
    rels_written = 0
    nodes_pruned = 0

    try:
        with driver.session() as session:
            if embeddings:
                for source_path, doc_chunks in grouped.items():
                    source_name = doc_chunks[0]["source_name"]

                    with session.begin_transaction() as tx:
                        tx.run(
                            "MATCH (c:Chunk {source_path: $sp}) DETACH DELETE c",
                            sp=source_path,
                        )
                        tx.run(
                            "MATCH (d:Document {source_path: $sp}) DETACH DELETE d",
                            sp=source_path,
                        )

                        tx.run(
                            """
                            CREATE (d:Document {
                                source_path: $sp,
                                source_name: $sn,
                                name: $name,
                                ingested_at: datetime()
                            })
                            """,
                            sp=source_path,
                            sn=source_name,
                            name=source_name,
                        )

                        for chunk in doc_chunks:
                            tx.run(
                                """
                                CREATE (c:Chunk {
                                    source_path: $sp,
                                    chunk_index: $idx,
                                    chunk_title: $title,
                                    content: $content,
                                    embedding: $embedding
                                })
                                """,
                                sp=source_path,
                                idx=chunk["chunk_index"],
                                title=chunk["chunk_title"] or "",
                                content=chunk["content"],
                                embedding=chunk["embedding"],
                            )

                        tx.run(
                            """
                            MATCH (d:Document {source_path: $sp}), (c:Chunk {source_path: $sp})
                            CREATE (c)-[:BELONGS_TO]->(d)
                            """,
                            sp=source_path,
                        )

                        tx.run(
                            """
                            MATCH (c1:Chunk {source_path: $sp}), (c2:Chunk {source_path: $sp})
                            WHERE c2.chunk_index = c1.chunk_index + 1
                            CREATE (c1)-[:NEXT]->(c2)
                            """,
                            sp=source_path,
                        )

                        tx.commit()

                    n = len(doc_chunks)
                    documents_written += 1
                    nodes_written += 1 + n
                    rels_written += n + max(0, n - 1)

            # Orphan prune: runs regardless of changes, but ONLY when sources were
            # actually collected (empty set => bad run, skip to avoid wiping the graph).
            if current_paths:
                # Exclude the aidlc-kb/ corpus (B37) — owned by aidlc_kb_ingest's own prune.
                result = session.run(
                    """
                    MATCH (n)
                    WHERE (n:Document OR n:Chunk)
                      AND NOT n.source_path IN $current
                      AND NOT n.source_path STARTS WITH 'aidlc-kb/'
                    DETACH DELETE n
                    RETURN count(n) AS pruned
                    """,
                    current=list(current_paths),
                )
                nodes_pruned = result.single()["pruned"]
            else:
                print(
                    "[neo4j_write] WARNING: current_paths is empty "
                    "(no sources collected) — skipping orphan prune."
                )

        skipped = not embeddings and nodes_pruned == 0

        return Output(
            {
                "documents_written": documents_written,
                "nodes_written": nodes_written,
                "relationships_written": rels_written,
                "nodes_pruned": nodes_pruned,
                "skipped": skipped,
            },
            metadata={
                "documents_written": MetadataValue.int(documents_written),
                "nodes_written": MetadataValue.int(nodes_written),
                "relationships_written": MetadataValue.int(rels_written),
                "nodes_pruned": MetadataValue.int(nodes_pruned),
            },
        )
    finally:
        driver.close()
