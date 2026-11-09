"""Neo4j store loader: build a graph from silver Parquet per a GraphSpec. node = {label, key, col?, props?};
edge = {rel, src: (label, key, col), dst: (label, key, col), props?, dst_list?, dst_list_key?}."""
import ast
import os

import pyarrow.parquet as pq

from weyland_pipeline._otel import traced_load  # B49(b) Phase 2 - one coarse span per dataset-load

from .store_common import downloaded, parquet_objects, record

_NEO4J_BATCH = 25_000        # load: one managed tx per batch (node MERGEs + edge CREATEs commit atomically)
_NEO4J_CLEAR_BATCH = 1_000   # clear: DETACH DELETE drags each node's edges into the tx, so keep batches small
# Neo4j RANGE indexes (which uniqueness constraints build) reject keys over ~8KB. A key column can carry a corrupt or
# oversized value (lastfm had a 120KB "artist name") that would abort the whole batch tx, so MERGE filters skip any
# row whose key stringifies longer than this. Chars (not bytes) × ≤4 bytes/char stays under the limit; real ids,
# names and titles are tiny, so this only ever drops garbage.
_KEY_MAXLEN = 1000


def _neo4j_driver():
    from neo4j import GraphDatabase

    uri = os.environ.get("NEO4J_URI", "bolt://neo4j.weyland.svc.cluster.local:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    pw = os.environ["NEO4J_PASSWORD"]   # secretKeyRef → neo4j-secret; no default (fail loud, no secret in code)
    # Resilience for the mesh: keep_alive + a short connection lifetime so stale Bolt connections are recycled, and
    # a generous transaction retry window so execute_write can re-establish a connection Envoy reset mid-load.
    return GraphDatabase.driver(uri, auth=(user, pw), keep_alive=True, max_connection_lifetime=120,
                                connection_acquisition_timeout=60, max_transaction_retry_time=180)


def _bt(name) -> str:
    """Backtick-quote a Cypher identifier (label / rel type / property / map key)."""
    return "`" + str(name).replace("`", "``") + "`"


def _key_ok(col):
    """The row guard every MERGE / MATCH key uses: present, and short enough for a RANGE index."""
    return f"row.{_bt(col)} IS NOT NULL AND size(toString(row.{_bt(col)})) <= {_KEY_MAXLEN}"


def _node_query(nd):
    label, key, col = nd["label"], nd["key"], nd.get("col", nd["key"])
    q = f"UNWIND $rows AS row WITH row WHERE {_key_ok(col)} MERGE (n:{_bt(label)} {{{_bt(key)}: row.{_bt(col)}}})"
    if nd.get("props"):
        q += " SET " + ", ".join(f"n.{_bt(p)} = row.{_bt(p)}" for p in nd["props"])
    return q


def _list_edge_query(ed):
    """dst is a multi-value list, PARSED to a real list in Python first (_parse_list). UNWIND it into one edge per
    element; dst is MERGE'd, the rel CREATE'd, src MATCH'd. With dst_list_key (track_genres → genre_id) the element
    keeps its real key type (int) so it MATCHes the int-keyed :Genre nodes; a plain scalar list (audioset
    human_labels) is toString'd, trimmed and size-guarded."""
    (sl, sk, sc), (dl, dk, dc) = ed["src"], ed["dst"]
    head = (f"UNWIND $rows AS row WITH row WHERE {_key_ok(sc)} AND row.{_bt(dc)} IS NOT NULL "
            f"MATCH (a:{_bt(sl)} {{{_bt(sk)}: row.{_bt(sc)}}}) ")
    if ed.get("dst_list_key"):
        each = f"UNWIND row.{_bt(dc)} AS _dv WITH a, _dv WHERE _dv IS NOT NULL "
    else:
        each = (f"UNWIND row.{_bt(dc)} AS _raw "
                f"WITH a, trim(toString(_raw)) AS _dv WHERE _dv <> '' AND size(_dv) <= {_KEY_MAXLEN} ")
    return head + each + f"MERGE (b:{_bt(dl)} {{{_bt(dk)}: _dv}}) CREATE (a)-[r:{_bt(ed['rel'])}]->(b)"


def _pair_edge_query(ed):
    """Both endpoints MATCHed (so every endpoint label must also be a node spec, loaded first), the rel CREATEd."""
    (sl, sk, sc), (dl, dk, dc) = ed["src"], ed["dst"]
    q = (f"UNWIND $rows AS row WITH row WHERE {_key_ok(sc)} AND {_key_ok(dc)} "
         f"MATCH (a:{_bt(sl)} {{{_bt(sk)}: row.{_bt(sc)}}}) "
         f"MATCH (b:{_bt(dl)} {{{_bt(dk)}: row.{_bt(dc)}}}) "
         f"CREATE (a)-[r:{_bt(ed['rel'])}]->(b)")
    if ed.get("props"):
        q += " SET " + ", ".join(f"r.{_bt(p)} = row.{_bt(p)}" for p in ed["props"])
    return q


def _neo4j_queries(spec):
    """Compile a GraphSpec into (constraint_cyphers, node_cyphers, edge_cyphers), built ONCE and reused for every
    batch. Nodes are UNWIND+MERGE (index-backed, dedup-safe). Edges are UNWIND+MATCH-both-endpoints+CREATE: MERGE'ing a
    relationship into a supernode is O(degree) per row (it scans the node's existing rels to dedup), death at scale
    (radiohead has ~40k listeners). CREATE is O(1); silver has one row per pair so there is no dup risk. A self-ref
    root whose parent isn't present just matches nothing and stays a root."""
    pairs = [(nd["label"], nd["key"]) for nd in spec.get("nodes", [])]
    for ed in spec.get("edges", []):
        pairs += [(ed["src"][0], ed["src"][1]), (ed["dst"][0], ed["dst"][1])]
    unique = list(dict.fromkeys(pairs))   # first-seen order, duplicates dropped
    constraints = [f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{_bt(label)}) REQUIRE n.{_bt(key)} IS UNIQUE"
                   for label, key in unique]
    node_q = [_node_query(nd) for nd in spec.get("nodes", [])]
    edge_q = [_list_edge_query(ed) if ed.get("dst_list") else _pair_edge_query(ed) for ed in spec.get("edges", [])]
    return constraints, node_q, edge_q


def _split_cell(s, key):
    """A stringified list cell → its items. ast.literal_eval keeps commas INSIDE an element intact (e.g.
    "['Speech', 'Inside, small room']"); a cell that is not a literal falls back to a bracket split, except when
    the elements must be dicts (nothing to split into)."""
    try:
        parsed = ast.literal_eval(s)
    except (ValueError, SyntaxError):
        if key is not None:
            return []
        return [p.strip(" '\"[]") for p in s.strip("[]").split(",") if p.strip(" '\"[]")]
    return list(parsed) if isinstance(parsed, (list, tuple)) else [parsed]


def _as_key(val):
    """Numeric-string ids become int so they MATCH int node keys (the :Genre genre_id)."""
    return int(val) if isinstance(val, str) and val.lstrip("-").isdigit() else val


def _parse_list(v, key=None):
    """Parse a multi-value cell into a list: a real list/tuple, or a stringified Python-list literal. key: when the
    elements are dicts (fma_tracks track_genres = "[{'genre_id': '21', ...}]"), extract this field from each."""
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        items = list(v)
    else:
        s = str(v).strip()
        items = _split_cell(s, key) if s else []
    if key is None:
        return [str(x) for x in items]
    values = (el.get(key) if isinstance(el, dict) else None for el in items)
    return [_as_key(val) for val in values if val is not None]


def _write_neo4j_batch(tx, node_q, edge_q, rows):
    """One batch = one managed transaction: node MERGEs + edge CREATEs commit together (atomic, so an execute_write
    RETRY after a dropped connection re-does the whole batch cleanly and never double-CREATEs edges)."""
    for q in node_q:
        tx.run(q, rows=rows)
    for q in edge_q:
        tx.run(q, rows=rows)


def _clear_graph(driver, spec, constraints, dataset, log):
    """Constraints first (MERGE without the backing index is O(n) per row: catastrophic on lastfm's ~17M), then a
    clean rebuild: edges are CREATE'd (no dedup), so a re-run MUST start empty or it doubles relationships. Batched
    DETACH DELETE keeps the wipe memory-bounded. A spec can set `clear_labels` to protect a label it SHARES with
    another dataset (fma_tracks reuses lastfm's :Artist; it clears only Track/Album)."""
    labels = [nd["label"] for nd in spec.get("nodes", [])]
    with driver.session() as s:
        for c in constraints:
            s.run(c)
        for label in spec.get("clear_labels", labels):
            log.info(f"neo4j {dataset}: clearing existing (:{label}) for clean rebuild")
            s.run(f"MATCH (n:{_bt(label)}) CALL {{ WITH n DETACH DELETE n }} "
                  f"IN TRANSACTIONS OF {_NEO4J_CLEAR_BATCH} ROWS")


def _load_graph_file(driver, path, queries, list_cols, key, log):
    """Feed one parquet file to the graph in batches: one auto-retried managed transaction per batch, which
    recovers from a Bolt connection Envoy reset mid-load, and whose atomicity means a retry can't double-CREATE."""
    node_q, edge_q = queries
    pf = pq.ParquetFile(path)
    log.info(f"neo4j {key.split('/')[0]}: columns {list(pf.schema_arrow.names)[:24]}")
    n = milestone = 0
    with driver.session() as s:
        for batch in pf.iter_batches(batch_size=_NEO4J_BATCH):
            rows = batch.to_pylist()
            for lc, lkey in list_cols:                 # parse stringified-list cols to real lists
                for r in rows:
                    r[lc] = _parse_list(r.get(lc), key=lkey)
            s.execute_write(_write_neo4j_batch, node_q, edge_q, rows)
            n += len(rows)
            if n // 1_000_000 > milestone:   # progress heartbeat every ~1M rows
                milestone = n // 1_000_000
                log.info(f"neo4j {key}: {n:,} rows loaded so far")
    return n


@traced_load
def _load_dataset_to_neo4j(driver, mc, cfg, dataset, spec, log) -> dict:
    """Build a graph from silver Parquet per the GraphSpec (idempotent: a clean rebuild each run). MEMORY-SAFE:
    temp file + row batches fed to batched UNWIND MERGE. One spec covers every parquet file under parquet/<dataset>/
    (they share the schema). Columns are logged so a spec/column mismatch is visible (a wrong key column filters
    every row out → 0 loaded, not a crash)."""
    constraints, node_q, edge_q = _neo4j_queries(spec)
    list_cols = [(ed["dst"][2], ed.get("dst_list_key")) for ed in spec.get("edges", []) if ed.get("dst_list")]
    _clear_graph(driver, spec, constraints, dataset, log)
    shape = f"{len(spec.get('nodes', []))} node type(s), {len(spec.get('edges', []))} edge type(s)"
    out = {}
    for name, stem in parquet_objects(mc, cfg, dataset):
        key = dataset if stem == dataset else f"{dataset}/{stem}"

        def load(name=name, key=key):
            with downloaded(mc, cfg, name) as path:
                n = _load_graph_file(driver, path, (node_q, edge_q), list_cols, key, log)
            log.info(f"neo4j {key}: {n:,} rows → {shape}")
            return n

        record(out, key, f"neo4j {dataset}", log, load)
    return out
