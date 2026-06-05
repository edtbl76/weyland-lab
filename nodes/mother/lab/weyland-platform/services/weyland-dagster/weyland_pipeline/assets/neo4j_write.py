from dagster import asset, Output, MetadataValue
from weyland_pipeline.resources import Neo4jResource


@asset(description="Write Document+Chunk nodes and relationships to Neo4j. No-op if content unchanged.")
def neo4j_write(
    source_document: dict,
    hash_check: dict,
    embeddings: list[dict],
    neo4j: Neo4jResource,
) -> Output[dict]:
    if not embeddings:
        return Output(
            {"nodes_written": 0, "skipped": True},
            metadata={"skipped_reason": MetadataValue.text("content unchanged")},
        )

    source_path = source_document["source_path"]
    source_name = source_document["source_name"]
    driver = neo4j.get_driver()

    try:
        with driver.session() as session:
            with session.begin_transaction() as tx:
                # Delete prior nodes for this source
                tx.run(
                    "MATCH (c:Chunk {source_path: $sp}) DETACH DELETE c",
                    sp=source_path,
                )
                tx.run(
                    "MATCH (d:Document {source_path: $sp}) DETACH DELETE d",
                    sp=source_path,
                )

                # Create Document node
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

                # Create Chunk nodes
                for chunk in embeddings:
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

                # BELONGS_TO relationships
                tx.run(
                    """
                    MATCH (d:Document {source_path: $sp}), (c:Chunk {source_path: $sp})
                    CREATE (c)-[:BELONGS_TO]->(d)
                    """,
                    sp=source_path,
                )

                # NEXT relationships (sequential chain)
                tx.run(
                    """
                    MATCH (c1:Chunk {source_path: $sp}), (c2:Chunk {source_path: $sp})
                    WHERE c2.chunk_index = c1.chunk_index + 1
                    CREATE (c1)-[:NEXT]->(c2)
                    """,
                    sp=source_path,
                )

                tx.commit()

        nodes = 1 + len(embeddings)
        rels = len(embeddings) + (len(embeddings) - 1)
        return Output(
            {"nodes_written": nodes, "relationships_written": rels, "skipped": False},
            metadata={
                "nodes_written": MetadataValue.int(nodes),
                "relationships_written": MetadataValue.int(rels),
            },
        )
    finally:
        driver.close()
