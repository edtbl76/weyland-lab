---
id: full-text-search
tags: [database, backend, pattern]
surfaces-at: [application-design, functional-design]
related: [semantic-search, database-indexing, query-optimization, vector-databases, filtering-and-sorting]
complexity: intermediate
---

# Full-Text Search

## What It Is
Search functionality that finds documents containing query terms through linguistic analysis — tokenization, stemming, stop-word removal, and relevance scoring — rather than exact string matching. Full-text search returns results ranked by relevance: "how well does this document match the query?" rather than "does this field equal this value?". It powers the search bars users expect in applications — finding products by description, articles by content, customers by name fragments. Full-text search is a distinct capability from relational filtering; it requires dedicated indexing structures (inverted indexes) and relevance algorithms (BM25, TF-IDF).

## When to Apply
- Search bars where users type natural language queries and expect relevant, ranked results
- Searching across large text fields (descriptions, notes, content bodies)
- Applications where typo tolerance, stemming ("running" matches "run"), and synonyms improve user experience
- When LIKE queries with wildcards are too slow or too inflexible for user-facing search
- Product search, document search, customer search, log search

## Key Concepts
- **Inverted Index**: The core data structure. Maps each unique term to the list of documents containing it. "apple" → [doc1, doc3, doc7]. Lookups are O(1) per term; relevance scoring ranks results. Building an inverted index is the fundamental operation of search engine indexing
- **Text Analysis Pipeline**: Before indexing and searching, text passes through an analyzer:
  - *Tokenizer*: Splits text into tokens ("quick brown fox" → ["quick", "brown", "fox"])
  - *Filters*: Lowercase, stop word removal ("the", "a", "is"), stemming ("running" → "run"), synonyms ("automobile" = "car")
  - Query text goes through the same pipeline — search terms are transformed to match index terms
- **Relevance Scoring**: BM25 (Best Match 25) is the industry-standard relevance algorithm. Factors: term frequency (TF — how often does the term appear in the document?), inverse document frequency (IDF — how rare is this term across all documents? Rare terms are more discriminating), and document length normalization
- **Elasticsearch**: The dominant full-text search engine. Built on Apache Lucene. Horizontally scalable, REST API, rich query DSL, supports aggregations for faceted search. Used for application search, log aggregation (ELK stack), and analytics. Managed services: AWS OpenSearch, Elastic Cloud
- **PostgreSQL Full-Text Search**: Built-in FTS via `tsvector` (indexed document), `tsquery` (search query), and `@@` operator. Supports stemming, stop words, and ranking (`ts_rank`). Performance is good for moderate data sizes. Avoids the operational overhead of a separate Elasticsearch cluster. Best for: applications already on PostgreSQL with moderate search volume
- **Faceted Search**: Search with filters and aggregations — "laptops under $500 with 4+ stars, brand: Apple or Dell". Elasticsearch aggregations make faceted search efficient. PostgreSQL can do this but with higher query complexity
- **Fuzzy Search**: Matching documents even when query terms contain typos. Levenshtein distance-based matching. Elasticsearch supports `fuzziness: AUTO`. PostgreSQL has `pg_trgm` extension for trigram similarity matching
- **Hybrid Search**: Combining full-text (BM25 keyword matching) with semantic search (vector similarity). Handles both exact keyword matches and semantic intent. Increasingly common in LLM-era applications. Elasticsearch and pgvector support hybrid search

## In Practice
Method applications use PostgreSQL FTS for simple search use cases on existing PostgreSQL databases (customer name search, product search in smaller catalogs). Elasticsearch (via AWS OpenSearch) is used when scale, faceting, or complex relevance tuning is required. The text analysis pipeline is configured to match the application's language requirements — custom synonym dictionaries for domain-specific terms. pgvector hybrid search is used in applications where semantic understanding supplements keyword matching.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Full-Text Search**: Don't use LIKE '%query%' for user-facing search — it's slow (full table scan, no index), returns no relevance ranking, and handles no linguistic variation. PostgreSQL's built-in FTS is good enough for most applications and avoids the operational burden of a separate Elasticsearch cluster; reach for Elasticsearch when you need scale, rich faceting, or relevance tuning that PostgreSQL can't provide. The text analysis pipeline (tokenization, stemming, stop words) is where most relevance quality comes from — invest in it early. Hybrid search (BM25 + vector) is the right answer for applications where "find me things about X" matters as much as "find me documents containing X". → `engineering-knowledge-repository/full-text-search.md`

## Related Entries
- [Semantic Search](semantic-search.md) — semantic search uses vector embeddings to find conceptually similar content; complements full-text keyword search
- [Database Indexing](database-indexing.md) — the inverted index is the specialized index structure that makes full-text search fast
- [Query Optimization](query-optimization.md) — full-text search queries require specialized optimization (index configuration, query planning)
- [Vector Databases](vector-databases.md) — vector databases power the semantic search component of hybrid search systems
- [Filtering and Sorting](filtering-and-sorting.md) — faceted search combines full-text search with structured filtering and aggregations
