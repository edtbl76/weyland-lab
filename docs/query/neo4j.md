# Neo4j — query cookbook

**Connect:**
- **Neo4j Browser** — `http://mother:30085` (HTTP NodePort), connect `bolt://mother:30086`, **encryption off**,
  `neo4j` / the Neo4j password (`neo4j-secret`). Import ready-made favorites: Favorites (★) → ⋮ → Import →
  [`neo4j-aidlc-favorites.csv`](neo4j-aidlc-favorites.csv) (lands in an "AIDLC" folder).
- **NeoDash** — `http://mother:30088`, same `bolt://mother:30086` / no-encryption. Dashboards persist as nodes in Neo4j.
- **In-pod** — `kubectl -n weyland exec -it deploy/neo4j -- cypher-shell -u neo4j -p <pw>`.
- **IntelliJ** — Neo4j driver, `bolt://mother:30086`.

> **Browser-side Bolt gotcha:** NeoDash/Browser connect from *your browser*, so use `bolt://mother:30086`
> (the NodePort) — NOT `neo4j.weyland.svc:7687` (unreachable from the LAN) — and encryption **off** (no TLS on
> the NodePort). Wrong host or encryption-on = "never connects".

Graphs here: the **AIDLC methodology** graph (B37), the **RAG/GraphRAG** graph, and the **dataset graphs** (B1 —
music: `fma_genres` genre tree + `lastfm` ~13.85M listen edges; fma_tracks/musicbrainz/audioset are follow-ons).
Importable Browser favorites: [AIDLC](neo4j-aidlc-favorites.csv) · [Music](neo4j-music-favorites.csv).
Importable NeoDash dashboard: [Music graph](neo4j-music-dashboard.json) (NeoDash → Load dashboard → paste/upload).


> **The CODE graph is not in here — yet.** `scripts/graphify.sh` builds an AST graph of this repo
> (13,051 nodes: Python, TypeScript, HCL) and graphify can emit it as Cypher with `--neo4j`. It was
> deliberately not loaded, because no question yet needs the code graph beside the data graph. The
> obvious candidate is a cross-graph query — *which code produces which dataset* — pairing with the
> B82 application taxonomy. Tracked as **EMA-208 (Low)**; plan in
> `docs/concepts/graphify-adoption.md`.
## Explore
```cypher
CALL db.labels();
CALL db.relationshipTypes();
MATCH (n) RETURN labels(n) AS label, count(*) AS n ORDER BY n DESC;
CALL db.schema.visualization();
```

## AIDLC methodology graph (B37)
`(:Entry {entry_id, complexity, vertical}) -[:RELATED_TO]-> (:Entry)`, and out to `:Stage` (`-[:SURFACES_AT]->`),
`:Tag` (`-[:TAGGED]->`), `:Vertical` (`-[:IN_VERTICAL]->`). Author-declared from frontmatter (no LLM).
```cypher
-- the internal cross-reference web (a NeoDash graph card)
MATCH p=(:Entry)-[:RELATED_TO]->(:Entry) RETURN p;

-- entries per vertical / stage / tag
MATCH (e:Entry)-[:IN_VERTICAL]->(v:Vertical) RETURN v.name AS vertical, count(e) AS n ORDER BY n DESC;
MATCH (e:Entry)-[:SURFACES_AT]->(s:Stage)    RETURN s.name AS stage,   count(e) AS n ORDER BY n DESC;
MATCH (e:Entry)-[:TAGGED]->(t:Tag)           RETURN t.name AS tag,     count(e) AS n ORDER BY n DESC LIMIT 25;

-- most-referenced entries (RELATED_TO in-degree)
MATCH (e:Entry)<-[:RELATED_TO]-(x) RETURN e.entry_id, count(x) AS refs ORDER BY refs DESC LIMIT 20;

-- gaps: entries with no vertical, or orphaned from the RELATED_TO web
MATCH (e:Entry) WHERE NOT (e)-[:IN_VERTICAL]->() RETURN e.entry_id;
MATCH (e:Entry) WHERE NOT (e)-[:RELATED_TO]-()   RETURN e.entry_id;
```
The full set (+ GDS) is in [`neo4j-aidlc-favorites.csv`](neo4j-aidlc-favorites.csv) — importable as Browser favorites.

## Dataset graphs — music (B1)
`(:Genre)-[:SUBGENRE_OF]->(:Genre)` (FMA genre taxonomy) and `(:User)-[:PLAYS {play_count}]->(:Artist)` (lastfm —
the count is an edge property). The full favorites set is [`neo4j-music-favorites.csv`](neo4j-music-favorites.csv).
```cypher
-- genre taxonomy tree (a NeoDash graph card)
MATCH p=(:Genre)-[:SUBGENRE_OF]->(:Genre) RETURN p;

-- top artists by listeners / by total plays
MATCH (:User)-[:PLAYS]->(a:Artist) RETURN a.name, count(*) AS listeners ORDER BY listeners DESC LIMIT 25;
MATCH (:User)-[r:PLAYS]->(a:Artist) RETURN a.name, sum(r.play_count) AS plays ORDER BY plays DESC LIMIT 25;

-- graph-native collaborative filtering: fans of X also listen to…
MATCH (a:Artist {name:'radiohead'})<-[:PLAYS]-(u:User)-[:PLAYS]->(rec:Artist)
WHERE rec <> a RETURN rec.name, count(DISTINCT u) AS shared_fans ORDER BY shared_fans DESC LIMIT 20;
```
> Edges are `CREATE`'d (not `MERGE`'d) into supernodes — MERGE-relationship is O(degree) and never finishes at
> this scale. And neo4j stays meshed via the `neo4j-bolt` DestinationRule (TCP keepalive) so long bulk-load
> Bolt connections don't half-open and hang.

## Dataset graphs — finance (company → SIC → filing, B113)

The EDGAR company graph: `(:Company {cik, ticker, company})-[:IN_INDUSTRY]->(:SIC {sic, sic_description})` +
`(:Company)-[:FILED]->(:Filing {accn, form, filed, report_date})`. ~49 mega-caps, 28 SIC industries, 1,144
10-K/10-Q filings. Loaded by `datasets_finance_neo4j_load` from the `company_meta` / `company_filings` silver.

```cypher
// industry peers: companies sharing an SIC, with their 10-K/10-Q filing counts
MATCH (c:Company)-[:IN_INDUSTRY]->(:SIC {sic_description: 'Semiconductors & Related Devices'})
OPTIONAL MATCH (c)-[:FILED]->(f:Filing)
RETURN c.ticker AS ticker, c.company AS company, count(f) AS filings ORDER BY filings DESC;

// most-recent 10-K per company
MATCH (c:Company)-[:FILED]->(f:Filing {form: '10-K'})
WITH c, f ORDER BY f.filed DESC
WITH c, collect(f)[0] AS latest
RETURN c.ticker, latest.accn, latest.filed ORDER BY latest.filed DESC LIMIT 15;

// industries ranked by company count
MATCH (:Company)-[:IN_INDUSTRY]->(s:SIC)
RETURN s.sic_description AS industry, count(*) AS companies ORDER BY companies DESC;
```

## RAG / GraphRAG graph
`(c:Chunk)-[:BELONGS_TO]->(d:Document)` with `(c1:Chunk)-[:NEXT]->(c2:Chunk)` chaining chunks in order. This is
the retrieval backbone the tool-server queries.
```cypher
-- documents by chunk count
MATCH (d:Document)<-[:BELONGS_TO]-(c:Chunk)
RETURN d.name, count(c) AS chunks ORDER BY chunks DESC LIMIT 20;

-- a document's chunk chain in order (swap source_path)
MATCH p=(c:Chunk {source_path: '<path>'})-[:NEXT*]->(:Chunk) RETURN p;

-- Entry nodes are ALSO Documents (B37 promotes them) — so bridge RAG ↔ methodology
MATCH (e:Entry)<-[:BELONGS_TO]-(c:Chunk) RETURN e.entry_id, count(c) AS chunks ORDER BY chunks DESC;
```

## GDS (graph data science — plugin installed)
```cypher
-- most CENTRAL methodology entries in the RELATED_TO web (project → score → drop)
CALL gds.graph.project('aidlc_rel', 'Entry', 'RELATED_TO');
CALL gds.pageRank.stream('aidlc_rel') YIELD nodeId, score
  RETURN gds.util.asNode(nodeId).entry_id AS entry, score ORDER BY score DESC LIMIT 20;
-- communities of related entries
CALL gds.louvain.stream('aidlc_rel') YIELD nodeId, communityId
  RETURN communityId, collect(gds.util.asNode(nodeId).entry_id) AS entries ORDER BY size(entries) DESC;
CALL gds.graph.drop('aidlc_rel');   -- cleanup (the projection is in-memory)
```

## Neo4j-isms
- **NeoDash graph cards** render any query returning a path (`RETURN p`). Table/bar cards want scalar columns.
- GDS projections live in memory — `project` → run algos → `drop`. Don't leave them around.
- APOC + GDS are both installed (`CALL apoc.help('')`, `CALL gds.list()`).
- Dashboards + favorites persist *in Neo4j itself* (`:_Neodash_Dashboard` nodes / Browser localStorage), so
  they survive restarts.
