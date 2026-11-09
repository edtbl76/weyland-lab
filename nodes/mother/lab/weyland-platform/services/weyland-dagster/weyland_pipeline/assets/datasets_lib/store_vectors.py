"""Vector store loaders: Qdrant, Weaviate and LanceDB. All three consume the same `_build_vectors` output
(records = [{id, vector, payload}]), built from silver Parquet by embedding text columns with bge-small or z-scoring
numeric features."""
import os

from . import io
from .store_common import PARQUET, downloaded, lakefs_base

_VEC_UPSERT_BATCH = 1_000
_EMBEDDER = None
_DEFAULT_DIM = 384
_LANCEDB_INDEX_MIN_ROWS = 2_000   # an IVF index only pays off past a few thousand rows


def _qdrant_client():
    from qdrant_client import QdrantClient

    host = os.environ.get("QDRANT_HOST", "qdrant.weyland.svc.cluster.local")
    port = int(os.environ.get("QDRANT_PORT", "6333"))
    return QdrantClient(host=host, port=port, timeout=300)   # 300s for the heavy one-time collection rewrites


def _weaviate_client():
    import weaviate

    host = os.environ.get("WEAVIATE_HOST", "weaviate.weyland.svc.cluster.local")
    return weaviate.connect_to_custom(
        http_host=host, http_port=int(os.environ.get("WEAVIATE_PORT", "8080")), http_secure=False,
        grpc_host=host, grpc_port=int(os.environ.get("WEAVIATE_GRPC_PORT", "50051")), grpc_secure=False)


def _embedder():
    """bge-small-en-v1.5 on raw ONNX Runtime (U13), loaded once per process. `.encode(...)` returns a 2-D array."""
    global _EMBEDDER
    if _EMBEDDER is None:
        from weyland_pipeline.resources.onnx_embedder import OnnxEmbedder

        _EMBEDDER = OnnxEmbedder(os.environ.get("EMBED_MODEL", "BAAI/bge-small-en-v1.5"))
    return _EMBEDDER


def _weaviate_class(domain, dataset):
    return "".join(p.capitalize() for p in f"datasets_{domain}_{dataset}".split("_"))


def _is_bounded(spec):
    return spec.get("cap") is not None or spec.get("filter") is not None


def _parquet_names(mc, cfg, prefix):
    return [o.object_name for o in mc.list_objects(cfg.repo, prefix=prefix, recursive=True)
            if o.object_name.endswith(PARQUET)]


def _concat(frames):
    import pandas as pd

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]


def _read_bounded_vector_frame(mc, cfg, dataset, spec, prefix, log):
    """BOUNDED read (projection + row cap): the fix for the whole-file `pd.read_parquet` that OOMs on OFF's
    4.5M × 211 all-string file. Fail-closes on 0 rows rather than building an empty collection."""
    from .parquet_read import needed_columns, read_capped

    if not (spec.get("text") or spec.get("numeric")):
        raise ValueError(f"{dataset}: a capped/filtered vector spec must declare `text` or `numeric` columns to "
                         f"project; got keys {sorted(spec)}")
    projection, filter_col, cap = needed_columns(spec), spec.get("filter"), spec.get("cap")
    frames, collected = [], 0
    for name in _parquet_names(mc, cfg, prefix):
        with downloaded(mc, cfg, name) as path:
            remaining = (cap - collected) if cap is not None else None
            frames.append(read_capped(path, projection, filter_col=filter_col, cap=remaining))
        collected += len(frames[-1])
        if cap is not None and collected >= cap:
            break  # cap reached: do not fetch or read any more files
    df = _concat(frames)
    if df.empty:
        raise ValueError(f"{dataset}: bounded read produced 0 rows (filter {filter_col!r}, cap {cap}) — refusing "
                         f"to build an empty collection rather than reporting a hydration that embedded nothing")
    log.info(f"{dataset}: bounded read → {len(df):,} rows, projected {list(df.columns)} (cap {cap}); building vectors…")
    return df


def _read_whole_vector_frame(mc, cfg, dataset, prefix, log):
    """Whole-file read of every silver parquet under `prefix`. None when no parquet is found (→ 0 records)."""
    import pandas as pd

    frames = []
    for name in _parquet_names(mc, cfg, prefix):
        with downloaded(mc, cfg, name) as path:
            frames.append(pd.read_parquet(path))
    if not frames:
        return None
    df = _concat(frames)
    log.info(f"{dataset}: read {len(frames)} parquet file(s) → {len(df):,} rows; building vectors…")  # B105 marker
    return df


def _read_vector_frame(mc, cfg, dataset, spec, prefix, log):
    """A capped/filtered spec does a BOUNDED read; every other spec reads whole files."""
    if _is_bounded(spec):
        return _read_bounded_vector_frame(mc, cfg, dataset, spec, prefix, log)
    return _read_whole_vector_frame(mc, cfg, dataset, prefix, log)


def _text_columns(df, spec, dataset, log):
    from .parquet_read import resolve_text_columns

    if not _is_bounded(spec):
        return [c for c in spec["text"] if c in df.columns]
    cols = resolve_text_columns(spec["text"], df.columns)  # fail closed: raises if ALL are absent
    absent = [c for c in spec["text"] if c not in cols]
    if absent:
        log.info(f"{dataset}: text columns absent from source, embedding without them: {absent}")
    return cols


def _text_vectors(df, spec, dataset, log):
    """Concatenate the text columns and embed with bge-small (already unit-normalized)."""
    cols = _text_columns(df, spec, dataset, log)
    texts = df[cols].fillna("").astype(str).agg(" ".join, axis=1).tolist()
    log.info(f"{dataset}: embedding {len(texts):,} texts (bge-small, batched — silent encode follows)…")  # B105
    vecs = _embedder().encode(texts, normalize_embeddings=True, batch_size=64, show_progress_bar=False)
    vectors = [v.tolist() for v in vecs]
    dim = len(vectors[0]) if vectors else _DEFAULT_DIM
    log.info(f"{dataset}: text vectors dim={dim} from {cols} ({len(df):,} rows)")
    return dim, vectors


def _numeric_vectors(df, spec, dataset, log):
    """Z-score the numeric feature columns: raw features span wild scales, so cosine similarity is meaningless
    without it."""
    import numpy as np
    import pandas as pd

    if spec.get("numeric"):
        cols = [c for c in spec["numeric"] if c in df.columns]
    else:
        excl = set(spec.get("numeric_exclude", [])) | ({spec["id"]} if spec.get("id") else set())
        cols = [c for c in df.columns if c not in excl and pd.api.types.is_numeric_dtype(df[c])]
    mat = df[cols].apply(pd.to_numeric, errors="coerce").fillna(0.0).to_numpy(dtype=float)
    mu, sd = mat.mean(axis=0), mat.std(axis=0)
    sd[sd == 0] = 1.0
    mat = np.nan_to_num((mat - mu) / sd, nan=0.0, posinf=0.0, neginf=0.0)
    log.info(f"{dataset}: numeric vectors dim={len(cols)} (z-scored) from {cols[:6]}… ({len(df):,} rows)")
    return len(cols), mat.tolist()


def _vectors_from_frame(df, spec, dataset, log):
    """(dim, vectors): text columns are embedded, otherwise numeric features are z-scored."""
    if spec.get("text"):
        return _text_vectors(df, spec, dataset, log)
    return _numeric_vectors(df, spec, dataset, log)


def _build_vectors(mc, cfg, dataset, spec, log):
    """(dim, records) for a dataset from silver Parquet: the SHARED step all three vector backends consume. Payload
    values are stringified (JSON / GraphQL-safe)."""
    from .parquet_read import build_records

    df = _read_vector_frame(mc, cfg, dataset, spec, f"{io.branch()}/parquet/{dataset}/", log)
    if df is None:
        return 0, []
    dim, vectors = _vectors_from_frame(df, spec, dataset, log)
    return dim, build_records(df, spec, vectors)


def _load_dataset_to_qdrant(client, dim, records, coll, log) -> int:
    """Recreate the collection (cosine) and upsert every record. Point id = sequential int (Qdrant ids must be
    int/UUID); the original id lives in the payload's row_id."""
    from qdrant_client.models import Distance, PointStruct, VectorParams

    client.recreate_collection(coll, vectors_config=VectorParams(size=dim, distance=Distance.COSINE))
    n = 0
    for s in range(0, len(records), _VEC_UPSERT_BATCH):
        chunk = records[s:s + _VEC_UPSERT_BATCH]
        pts = [PointStruct(id=s + j, vector=r["vector"], payload=r["payload"]) for j, r in enumerate(chunk)]
        client.upsert(collection_name=coll, points=pts)
        n += len(pts)
    log.info(f"qdrant {coll}: {n:,} points (dim {dim})")
    return n


def _payload_keys(records):
    return list(records[0]["payload"].keys()) if records else ["row_id"]


def _load_dataset_to_weaviate(client, dim, records, cls, log) -> int:
    """Drop + recreate the class (BYO vectors, vectorizer none) and batch-insert. Payload keys → TEXT props.
    Returns what LANDED, not what was attempted: the dynamic batch collects rejected objects on
    `col.batch.failed_objects` instead of raising (OFF's messier text dropped ~4,208 of 200k on the git-6df37f41
    hydration), so the drop is surfaced loudly."""
    from weaviate.classes.config import Configure, DataType, Property

    if cls in {c.name for c in client.collections.list_all().values()}:
        client.collections.delete(cls)
    client.collections.create(
        name=cls, vectorizer_config=Configure.Vectorizer.none(),
        properties=[Property(name=k, data_type=DataType.TEXT) for k in _payload_keys(records)])
    col = client.collections.get(cls)
    n = 0
    with col.batch.dynamic() as batch:
        for r in records:
            batch.add_object(properties=r["payload"], vector=r["vector"])
            n += 1
    failed = col.batch.failed_objects
    landed = n - len(failed)
    if failed:
        log.warning(f"weaviate {cls}: {len(failed):,} of {n:,} objects FAILED to insert (landed "
                    f"{landed:,}) — first error: {failed[0].message}")
    log.info(f"weaviate {cls}: {landed:,} objects landed (dim {dim})")
    return landed


def _lancedb_connect(cfg):
    """Open a LanceDB database on the lakeFS S3 gateway. LanceDB is EMBEDDED (no server): it reads and writes Lance
    datasets straight from object storage. One db per domain at s3://<repo>/<branch>/lancedb/, a table per dataset."""
    import lancedb

    scheme, base = lakefs_base()
    storage_options = {
        "aws_endpoint": base,
        "aws_access_key_id": os.environ["LAKEFS_ACCESS_KEY_ID"],
        "aws_secret_access_key": os.environ["LAKEFS_SECRET_ACCESS_KEY"],
        "aws_region": "us-east-1",
        "aws_allow_http": "false" if scheme == "https" else "true",   # the in-cluster gateway is plain HTTP
        "aws_virtual_hosted_style_request": "false",   # path-style: the lakeFS / MinIO S3 gateway
    }
    return lancedb.connect(f"s3://{cfg.repo}/{io.branch()}/lancedb", storage_options=storage_options)


def _load_dataset_to_lancedb(db, dim, records, table, log) -> int:
    """Drop + recreate a LanceDB table (row_id + fixed-size vector + payload). Builds an ANN index when the table is
    large enough (small tables do exact search fine)."""
    import pyarrow as pa

    if table in db.table_names():
        db.drop_table(table)
    flat = pa.array([x for r in records for x in r["vector"]], type=pa.float32())
    arrays = {"vector": pa.FixedSizeListArray.from_arrays(flat, dim)}
    for k in _payload_keys(records):
        arrays[k] = pa.array([str(r["payload"].get(k, "")) for r in records], type=pa.string())
    tbl = db.create_table(table, pa.table(arrays))
    try:
        if len(records) >= _LANCEDB_INDEX_MIN_ROWS:
            tbl.create_index(metric="cosine", vector_column_name="vector")
    except Exception as e:  # noqa: BLE001 - the index is an optimization; exact search works without it
        log.warning(f"lancedb {table}: index skipped ({e})")
    log.info(f"lancedb {table}: {len(records):,} rows (dim {dim})")
    return len(records)
