"""Custom DataHub emitter for the Dagster asset catalog + lineage.

Replaces the acryl-datahub-dagster-plugin sensor: its `datahub_sensor` is built on
Dagster's `run_status_sensor`, which is broken on Dagster 1.7.3+ (dagster#21526) and so
never emits on our 1.13.10 — confirmed: "Checking for new runs... skipped" every tick
even at zero run volume, indices stay at 0. This instead walks the asset graph directly
and pushes Dataset (name + description + group) + UpstreamLineage + a group tag to GMS via
the REST emitter. No sensor, no cursor, version-proof. Idempotent (DataHub upserts).

Note: most Dagster assets aren't tabular (embeddings, vector/graph writes) and carry no
TableSchema, so we emit no column schema for the dagster-platform datasets. The two tabular
products (model_catalog, eval_scores) get real column schemas on their *iceberg*-platform
datasets via the DataHub Iceberg source; iceberg_publish.py emits the cross-platform lineage
edge that links the dagster asset to its iceberg table.

Run standalone:  python -m weyland_pipeline.datahub_emit
"""
import os
from typing import Dict, List, NamedTuple, Optional, Set

from dagster import AssetKey
from datahub.emitter.mce_builder import make_chart_urn, make_dashboard_urn, make_dataset_urn, make_tag_urn
from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.metadata.schema_classes import (
    AuditStampClass,
    BooleanTypeClass,
    ChangeAuditStampsClass,
    ChartInfoClass,
    DashboardInfoClass,
    DatasetLineageTypeClass,
    DatasetPropertiesClass,
    GlobalTagsClass,
    NumberTypeClass,
    OtherSchemaClass,
    SchemaFieldClass,
    SchemaFieldDataTypeClass,
    SchemaMetadataClass,
    StringTypeClass,
    TagAssociationClass,
    UpstreamClass,
    UpstreamLineageClass,
)

from weyland_pipeline.assets import all_assets

PLATFORM = "dagster"
ENV = "PROD"


class AssetInfo(NamedTuple):
    deps: Set[AssetKey]
    description: Optional[str]
    group: Optional[str]


def _name(key: AssetKey) -> str:
    return ".".join(key.path)


def _asset_info() -> Dict[AssetKey, AssetInfo]:
    """asset_key -> (upstream keys, description, group), walking every AssetsDefinition."""
    info: Dict[AssetKey, AssetInfo] = {}
    for ad in all_assets:
        per_key = getattr(ad, "asset_deps", None) or {}
        descs = getattr(ad, "descriptions_by_key", {}) or {}
        groups = getattr(ad, "group_names_by_key", {}) or {}
        keys = set(per_key.keys()) | set(getattr(ad, "keys", []) or [])
        for key in keys:
            cur = info.get(key, AssetInfo(set(), None, None))
            cur.deps.update(per_key.get(key, set()))
            info[key] = AssetInfo(
                deps=cur.deps,
                description=descs.get(key) or cur.description,
                group=groups.get(key) or cur.group,
            )
    return info


def build_mcps() -> List[MetadataChangeProposalWrapper]:
    info = _asset_info()
    mcps: List[MetadataChangeProposalWrapper] = []
    for key, ai in info.items():
        urn = make_dataset_urn(platform=PLATFORM, name=_name(key), env=ENV)
        mcps.append(
            MetadataChangeProposalWrapper(
                entityUrn=urn,
                aspect=DatasetPropertiesClass(
                    name=_name(key),
                    description=ai.description,
                    customProperties={"dagster_group": ai.group} if ai.group else {},
                ),
            )
        )
        if ai.group:
            mcps.append(
                MetadataChangeProposalWrapper(
                    entityUrn=urn,
                    aspect=GlobalTagsClass(
                        tags=[TagAssociationClass(tag=make_tag_urn(ai.group))]
                    ),
                )
            )
        if ai.deps:
            upstreams = [
                UpstreamClass(
                    dataset=make_dataset_urn(platform=PLATFORM, name=_name(u), env=ENV),
                    type=DatasetLineageTypeClass.TRANSFORMED,
                )
                for u in sorted(ai.deps, key=_name)
            ]
            mcps.append(
                MetadataChangeProposalWrapper(
                    entityUrn=urn, aspect=UpstreamLineageClass(upstreams=upstreams)
                )
            )
    return mcps


def _field_type(type_str) -> SchemaFieldDataTypeClass:
    # substring match (lowercased) so it handles pyarrow ("int64", "double"), Weaviate ("DataType.INT",
    # "DataType.TEXT"), and similar type strings uniformly.
    s = str(type_str).lower()
    if any(t in s for t in ("int", "long", "short", "byte", "double", "float", "decimal", "number")):
        return SchemaFieldDataTypeClass(type=NumberTypeClass())
    if "bool" in s:
        return SchemaFieldDataTypeClass(type=BooleanTypeClass())
    return SchemaFieldDataTypeClass(type=StringTypeClass())


def _field_type_from_value(v) -> SchemaFieldDataTypeClass:
    if isinstance(v, bool):
        return SchemaFieldDataTypeClass(type=BooleanTypeClass())
    if isinstance(v, (int, float)):
        return SchemaFieldDataTypeClass(type=NumberTypeClass())
    return SchemaFieldDataTypeClass(type=StringTypeClass())


def _store_aspects(name, platform, description, fields, producer_asset, props=None):
    """Common aspect set for a custom-emitted store dataset: props + (schema) + group tag + lineage."""
    aspects = [
        DatasetPropertiesClass(name=name, description=description, customProperties=props or {}),
        GlobalTagsClass(tags=[TagAssociationClass(tag=make_tag_urn("default"))]),
        UpstreamLineageClass(
            upstreams=[
                UpstreamClass(
                    dataset=make_dataset_urn(platform=PLATFORM, name=producer_asset, env=ENV),
                    type=DatasetLineageTypeClass.TRANSFORMED,
                )
            ]
        ),
    ]
    if fields:
        aspects.insert(
            1,
            SchemaMetadataClass(
                schemaName=name, platform=f"urn:li:dataPlatform:{platform}", version=0, hash="",
                platformSchema=OtherSchemaClass(rawSchema=""), fields=fields,
            ),
        )
    return aspects


DBT_MANIFEST = os.environ.get("DBT_MANIFEST", "/app/dbt/target/manifest.json")


def _iceberg_name(node) -> str:
    """`iceberg.<schema>.<table>` — the fully-qualified Trino/Iceberg name for a dbt node (mart or source),
    matching how the marts materialize (database=iceberg, schema=dbt) and how the gold sources are read."""
    db = node.get("database") or "iceberg"
    schema = node.get("schema") or "dbt"
    ident = node.get("identifier") or node.get("alias") or node.get("name")
    return f"{db}.{schema}.{ident}"


def emit_dbt():
    """Custom-emit the dbt transform tier from the baked `manifest.json` (no Trino/DB connection needed).
    Each materialized mart → a Trino/Iceberg Dataset (`iceberg.dbt.mart_*`) carrying its description, per-column
    docs, a `dbt` tag, and UpstreamLineage to the gold source tables it reads (walking THROUGH the ephemeral
    staging models to the real `source.*` nodes). The gold sources are emitted too (thin props + a `gold` tag) so
    the lineage nodes aren't bare stubs. Returns (n_marts, [mart names]). Mirrors the DataHub dbt source but
    stays offline + version-proof, like the other custom emitters here."""
    import json

    with open(DBT_MANIFEST) as f:
        manifest = json.load(f)
    nodes, sources = manifest.get("nodes", {}), manifest.get("sources", {})

    def _source_ancestors(uid, seen=None):
        """All `source.*` unique_ids reachable from `uid` by walking depends_on through ephemeral models."""
        seen = seen if seen is not None else set()
        node = nodes.get(uid)
        if not node:
            return set()
        found = set()
        for dep in node.get("depends_on", {}).get("nodes", []):
            if dep in seen:
                continue
            seen.add(dep)
            if dep.startswith("source."):
                found.add(dep)
            elif dep in nodes:
                found |= _source_ancestors(dep, seen)
        return found

    emitter = _gms_emitter()
    emitted_sources = set()
    marts = []
    for uid, node in nodes.items():
        if node.get("resource_type") != "model" or node.get("config", {}).get("materialized") == "ephemeral":
            continue  # skip ephemeral staging — only real (materialized) marts get their own Iceberg table
        name = _iceberg_name(node)
        urn = make_dataset_urn(platform="trino", name=name, env=ENV)
        fields = [
            SchemaFieldClass(fieldPath=col, type=_field_type(meta.get("data_type") or "string"),
                             nativeDataType=str(meta.get("data_type") or "unknown"),
                             description=meta.get("description") or None)
            for col, meta in node.get("columns", {}).items()
        ]
        aspects = [
            DatasetPropertiesClass(name=node["name"], description=node.get("description") or "dbt mart",
                                   customProperties={"materialized": node.get("config", {}).get("materialized", ""),
                                                     "dbt_unique_id": uid}),
            GlobalTagsClass(tags=[TagAssociationClass(tag=make_tag_urn("dbt"))]),
        ]
        if fields:
            aspects.append(SchemaMetadataClass(
                schemaName=name, platform="urn:li:dataPlatform:trino", version=0, hash="",
                platformSchema=OtherSchemaClass(rawSchema=""), fields=fields))
        upstreams = []
        for src_uid in _source_ancestors(uid):
            src = sources.get(src_uid)
            if not src:
                continue
            src_urn = make_dataset_urn(platform="trino", name=_iceberg_name(src), env=ENV)
            upstreams.append(UpstreamClass(dataset=src_urn, type=DatasetLineageTypeClass.TRANSFORMED))
            if src_uid not in emitted_sources:  # thin catalog entry for the gold source so it's not a bare stub
                for asp in (DatasetPropertiesClass(name=src["name"],
                                                   description=src.get("description") or "Iceberg gold table (dbt source)"),
                            GlobalTagsClass(tags=[TagAssociationClass(tag=make_tag_urn("gold"))])):
                    emitter.emit(MetadataChangeProposalWrapper(entityUrn=src_urn, aspect=asp))
                emitted_sources.add(src_uid)
        if upstreams:
            aspects.append(UpstreamLineageClass(upstreams=upstreams))
        for aspect in aspects:
            emitter.emit(MetadataChangeProposalWrapper(entityUrn=urn, aspect=aspect))
        marts.append(node["name"])
    return len(marts), marts


# Feast offline source table (feast Postgres DB) ← the dbt mart it's loaded from (feast_setup._load_offline_sources).
# The dbt connector can't draw this (cross-system, downstream of the marts); the postgres recipe catalogs the
# `feast` DB's columns → this adds the missing UpstreamLineage so DataHub shows gold → mart → Feast source.
_FEAST_SOURCES = {
    "track_audio_features": "mart_spotify_audio",
    "state_health_risk": "mart_state_health_trends",
}


def emit_feast():
    """Emit the mart → Feast-source lineage edge. Each Feast offline source is a table in the `feast` Postgres DB
    (`feast.public.<table>`, cataloged by the postgres recipe); this points its UpstreamLineage at the dbt mart
    that feast_setup loads it from (`iceberg.dbt.<mart>` on Trino) + a `feast` tag, completing gold → mart → Feast
    in one graph. Returns (count, [table names])."""
    emitter = _gms_emitter()
    names = []
    for table, mart in _FEAST_SOURCES.items():
        urn = make_dataset_urn(platform="postgres", name=f"feast.public.{table}", env=ENV)
        mart_urn = make_dataset_urn(platform="trino", name=f"iceberg.dbt.{mart}", env=ENV)
        aspects = [
            DatasetPropertiesClass(name=table,
                                   description=f"Feast offline source — loaded from the dbt mart {mart} by "
                                               f"feast_setup._load_offline_sources; read by Feast via "
                                               f"PostgreSQLSource. The dbt mart is the source of truth."),
            GlobalTagsClass(tags=[TagAssociationClass(tag=make_tag_urn("feast"))]),
            UpstreamLineageClass(upstreams=[
                UpstreamClass(dataset=mart_urn, type=DatasetLineageTypeClass.TRANSFORMED)]),
        ]
        for aspect in aspects:
            emitter.emit(MetadataChangeProposalWrapper(entityUrn=urn, aspect=aspect))
        names.append(table)
    return len(names), names


def emit_lightdash():
    """Custom-emit Lightdash dashboards + charts to DataHub (this DataHub has NO UI managed-ingestion, so the BI
    layer is cataloged here like the stores). Each saved chart → a DataHub Chart with lineage to its dbt mart
    (`iceberg.dbt.<tableName>` on the `trino` platform — the SAME URN emit_dbt emits, so chart→mart links up);
    each dashboard → a DataHub Dashboard listing its charts. Completes gold → dbt mart → Lightdash chart in the
    graph. No-ops (returns (0, 0)) if LIGHTDASH_API_KEY is unset. Returns (n_charts, n_dashboards)."""
    import time

    import requests

    key = os.environ.get("LIGHTDASH_API_KEY", "")
    if not key:
        return 0, 0
    base = os.environ.get("LIGHTDASH_URL", "http://lightdash.data-mesh.svc.cluster.local:8080").rstrip("/")
    s = requests.Session()
    s.headers.update({"Authorization": f"ApiKey {key}"})

    def g(path):
        r = s.get(f"{base}{path}", timeout=30)
        r.raise_for_status()
        return r.json()["results"]

    emitter = _gms_emitter()
    now = int(time.time() * 1000)
    stamp = ChangeAuditStampsClass(created=AuditStampClass(time=now, actor="urn:li:corpuser:datahub"),
                                   lastModified=AuditStampClass(time=now, actor="urn:li:corpuser:datahub"))
    proj = g("/api/v1/org/projects")[0]["projectUuid"]
    chart_urn, n_c, n_d = {}, 0, 0
    for summary in g(f"/api/v1/projects/{proj}/spaces"):
        # the /spaces list is summaries (counts only) — fetch the full space for its queries + dashboards.
        sp = g(f"/api/v1/projects/{proj}/spaces/{summary['uuid']}")
        space_name = sp.get("name", "")
        for q in sp.get("queries", []):
            cid = q["uuid"]
            cname = q.get("name") or cid
            try:
                table = g(f"/api/v1/saved/{cid}").get("tableName")
            except Exception:  # noqa: BLE001 — a chart lookup failing must not sink the whole emit
                table = None
            inputs = [make_dataset_urn(platform="trino", name=f"iceberg.dbt.{table}", env=ENV)] if table else []
            urn = make_chart_urn("lightdash", cid)
            chart_urn[cid] = urn
            emitter.emit(MetadataChangeProposalWrapper(entityUrn=urn, aspect=ChartInfoClass(
                title=cname, description=space_name, lastModified=stamp,
                chartUrl=f"{base}/projects/{proj}/saved/{cid}/view", inputs=inputs)))
            n_c += 1
        for d in sp.get("dashboards", []):
            did = d["uuid"]
            dname = d.get("name") or did
            try:
                tiles = g(f"/api/v1/dashboards/{did}").get("tiles", [])
                cids = [t["properties"]["savedChartUuid"] for t in tiles
                        if t.get("type") == "saved_chart" and t.get("properties", {}).get("savedChartUuid")]
            except Exception:  # noqa: BLE001
                cids = []
            emitter.emit(MetadataChangeProposalWrapper(
                entityUrn=make_dashboard_urn("lightdash", did),
                aspect=DashboardInfoClass(title=dname, description=space_name, lastModified=stamp,
                                          charts=[chart_urn[c] for c in cids if c in chart_urn],
                                          dashboardUrl=f"{base}/projects/{proj}/dashboards/{did}/view")))
            n_d += 1
    return n_c, n_d


def _gms_emitter() -> DatahubRestEmitter:
    server = os.environ.get("DATAHUB_GMS_URL", "http://datahub-datahub-gms.data-mesh.svc.cluster.local:8080")
    return DatahubRestEmitter(gms_server=server, token=os.environ.get("DATAHUB_GMS_TOKEN", ""))


def _vector_dataset_meta(name, backend):
    """If this is a datasets_* vector collection/class (not a RAG one), return (description, producer_asset) so
    it's cataloged as a dataset-domain vector store with lineage ← its loader (datasets_<dom>_<backend>_load);
    else None → the RAG defaults. Qdrant names are `datasets_<dom>_<ds>`, Weaviate classes `Datasets<Dom>…`."""
    low = name.lower()
    for dom in ("music", "health"):
        if low.startswith(f"datasets_{dom}") or low.startswith(f"datasets{dom}"):
            kind = "collection" if backend == "qdrant" else "class"
            return (f"{dom.capitalize()} dataset vector {kind} ({backend}) — similarity search over silver "
                    f"features/text (datasets_lib vector loader).",
                    f"datasets_{dom}_{backend}_load")
    return None


def emit_qdrant():
    """Custom-emit one DataHub Dataset per Qdrant collection (props + a payload schema sampled from one point).
    RAG collections get lineage ← qdrant_write; datasets_* collections ← their vector loader. Returns
    (count, [collection names])."""
    from qdrant_client import QdrantClient

    emitter = _gms_emitter()
    client = QdrantClient(
        host=os.environ.get("QDRANT_HOST", "qdrant.weyland.svc.cluster.local"),
        port=int(os.environ.get("QDRANT_PORT", "6333")),
    )
    names = []
    for coll in client.get_collections().collections:
        name = coll.name
        props, fields = {}, []
        try:
            info = client.get_collection(name)
            props["points_count"] = str(info.points_count)
            vec = info.config.params.vectors
            if hasattr(vec, "size"):
                props["vector_size"], props["distance"] = str(vec.size), str(vec.distance)
        except Exception:  # noqa: BLE001
            pass
        try:
            pts, _ = client.scroll(collection_name=name, limit=1, with_payload=True, with_vectors=False)
            if pts and pts[0].payload:
                fields = [
                    SchemaFieldClass(fieldPath=k, type=_field_type_from_value(v), nativeDataType=type(v).__name__)
                    for k, v in pts[0].payload.items()
                ]
        except Exception:  # noqa: BLE001
            pass
        urn = make_dataset_urn(platform="qdrant", name=name, env=ENV)
        meta = _vector_dataset_meta(name, "qdrant")
        desc, producer = meta if meta else ("Qdrant vector collection (RAG dense backend).", "qdrant_write")
        for aspect in _store_aspects(name, "qdrant", desc, fields, producer, props):
            emitter.emit(MetadataChangeProposalWrapper(entityUrn=urn, aspect=aspect))
        names.append(name)
    return len(names), names


def emit_weaviate():
    """Custom-emit one DataHub Dataset per Weaviate collection/class (class properties as schema) with
    lineage ← weaviate_write. Returns (count, [class names])."""
    import weaviate

    emitter = _gms_emitter()
    host = os.environ.get("WEAVIATE_HOST", "weaviate.weyland.svc.cluster.local")
    client = weaviate.connect_to_custom(
        http_host=host, http_port=int(os.environ.get("WEAVIATE_PORT", "8080")), http_secure=False,
        grpc_host=host, grpc_port=int(os.environ.get("WEAVIATE_GRPC_PORT", "50051")), grpc_secure=False,
    )
    names = []
    try:
        for cfg in client.collections.list_all().values():
            name = cfg.name
            fields = [
                SchemaFieldClass(fieldPath=p.name, type=_field_type(p.data_type), nativeDataType=str(p.data_type))
                for p in (cfg.properties or [])
            ]
            urn = make_dataset_urn(platform="weaviate", name=name, env=ENV)
            meta = _vector_dataset_meta(name, "weaviate")
            desc, producer = meta if meta else ("Weaviate vector class (RAG dense backend).", "weaviate_write")
            for aspect in _store_aspects(name, "weaviate", desc, fields, producer):
                emitter.emit(MetadataChangeProposalWrapper(entityUrn=urn, aspect=aspect))
            names.append(name)
    finally:
        client.close()
    return len(names), names


def emit_lancedb():
    """Custom-emit LanceDB tables as DataHub Datasets (platform lancedb) with schema (vector col + payload) +
    lineage ← datasets_<dom>_lancedb_load. LanceDB is EMBEDDED (no server) — we connect in-process per domain
    over the lakeFS S3 gateway (same as the loader) and read each table's Arrow schema. Returns (count, names)."""
    from weyland_pipeline.assets.datasets_lib.loaders import _lancedb_connect
    from weyland_pipeline.assets.datasets_health_transform import HEALTH_CFG
    from weyland_pipeline.assets.datasets_music_transform import MUSIC_CFG

    emitter = _gms_emitter()
    names = []
    for cfg in (MUSIC_CFG, HEALTH_CFG):
        if not (cfg.lancedb_allow or cfg.vector_allow):
            continue
        db = _lancedb_connect(cfg)
        lt = db.list_tables()
        table_names = lt.tables if hasattr(lt, "tables") else list(lt)
        for table in table_names:
            schema = db.open_table(table).schema
            fields = [
                SchemaFieldClass(fieldPath=f.name, type=_field_type(str(f.type)), nativeDataType=str(f.type))
                for f in schema
            ]
            name = f"datasets_{cfg.domain}_{table}"
            urn = make_dataset_urn(platform="lancedb", name=name, env=ENV)
            for aspect in _store_aspects(
                name, "lancedb",
                f"LanceDB table ({cfg.domain}) — embedded, Lance-native vector store on the lakeFS S3 gateway "
                "(ANN search in-process, no server).",
                fields, f"datasets_{cfg.domain}_lancedb_load",
            ):
                emitter.emit(MetadataChangeProposalWrapper(entityUrn=urn, aspect=aspect))
            names.append(name)
    return len(names), names


def emit_lakefs():
    """Custom-emit a DataHub Dataset per lakeFS repository (storage namespace + default branch + latest
    commit, with lineage ← datasets_commit). No native DataHub connector for lakeFS. Returns (count, names)."""
    import lakefs

    client = lakefs.Client(
        host=os.environ.get("LAKEFS_ENDPOINT", "http://lakefs.data-mesh.svc.cluster.local:8000"),
        username=os.environ["LAKEFS_ACCESS_KEY_ID"],
        password=os.environ["LAKEFS_SECRET_ACCESS_KEY"],
    )
    emitter = _gms_emitter()
    names = []
    for repo in lakefs.repositories(client=client):
        rid = repo.id
        props = {}
        try:
            rp = repo.properties
            props["storage_namespace"] = rp.storage_namespace
            props["default_branch"] = rp.default_branch
            head = repo.branch(rp.default_branch).head.get_commit()
            props["latest_commit"] = head.id[:12]
            props["latest_message"] = head.message or ""
        except Exception:  # noqa: BLE001
            pass
        urn = make_dataset_urn(platform="lakefs", name=rid, env=ENV)
        for aspect in _store_aspects(rid, "lakefs",
                                     "lakeFS repository (git-for-data: versioned object store over MinIO).",
                                     [], "datasets_commit", props):
            emitter.emit(MetadataChangeProposalWrapper(entityUrn=urn, aspect=aspect))
        names.append(rid)
    return len(names), names


def emit_opensearch():
    """Custom-emit a DataHub Dataset per OpenSearch index (mapping → schema). The standalone instance runs
    with security DISABLED, so plain HTTP, no creds. Skips system indices. Sample/external indices have no
    pipeline lineage (a future corpus index would get lineage ← its writer). Returns (count, names)."""
    import json
    import urllib.request

    base = os.environ.get("OPENSEARCH_ENDPOINT", "http://opensearch-cluster-master.opensearch.svc.cluster.local:9200")
    emitter = _gms_emitter()
    with urllib.request.urlopen(f"{base}/_cat/indices?format=json&h=index", timeout=30) as r:
        indices = [d["index"] for d in json.load(r)]
    names = []
    for idx in indices:
        if idx.startswith((".", "security", "opensearch_dashboards")):
            continue  # system / internal / built-in sample-data (opensearch_dashboards_sample_*) indices
        fields = []
        try:
            with urllib.request.urlopen(f"{base}/{idx}/_mapping", timeout=30) as r:
                mp = json.load(r).get(idx, {}).get("mappings", {}).get("properties", {})
            fields = [
                SchemaFieldClass(fieldPath=k, type=_field_type(v.get("type", "object")),
                                 nativeDataType=v.get("type", "object"))
                for k, v in mp.items()
            ]
        except Exception:  # noqa: BLE001
            pass
        urn = make_dataset_urn(platform="opensearch", name=idx, env=ENV)
        aspects = [
            DatasetPropertiesClass(name=idx, description="OpenSearch index (lexical/BM25 search backend).",
                                   customProperties={}),
            GlobalTagsClass(tags=[TagAssociationClass(tag=make_tag_urn("default"))]),
        ]
        if fields:
            aspects.insert(1, SchemaMetadataClass(
                schemaName=idx, platform="urn:li:dataPlatform:opensearch", version=0, hash="",
                platformSchema=OtherSchemaClass(rawSchema=""), fields=fields))
        for aspect in aspects:
            emitter.emit(MetadataChangeProposalWrapper(entityUrn=urn, aspect=aspect))
        names.append(idx)
    return len(names), names


def emit_duckdb():
    """Custom-emit the GizmoSQL/DuckDB Flight SQL silver TABLES as DataHub Datasets (platform duckdb) with
    schema (from information_schema) + lineage ← the parquet datasets they materialise. Connects to the live
    GizmoSQL server over Arrow Flight SQL. The silver lives as persisted tables in the per-domain schemas
    (datasets_music / datasets_health), not views in main — see scripts/gen_gizmosql_init.py. Returns (count, names)."""
    import adbc_driver_flightsql.dbapi as flight_sql

    # Plaintext grpc+tcp: GizmoSQL runs TLS-off and Istio mTLS secures the in-cluster hop (both pods meshed),
    # so there's no app TLS to skip-verifying. GIZMOSQL_URI in the pod env must also be grpc+tcp.
    conn = flight_sql.connect(
        os.environ.get("GIZMOSQL_URI", "grpc+tcp://gizmosql.data-mesh.svc.cluster.local:31337"),
        db_kwargs={
            "username": os.environ.get("GIZMOSQL_USERNAME", "weyland"),
            "password": os.environ["GIZMOSQL_PASSWORD"],
        },
    )
    emitter = _gms_emitter()
    names = []
    try:
        cur = conn.cursor()
        # the silver is materialised as base TABLES in the per-domain schemas (datasets_music/_health);
        # skip main + GizmoSQL's internal/system schemas.
        cur.execute(
            "SELECT table_schema, table_name FROM information_schema.tables "
            "WHERE table_schema LIKE 'datasets_%' ORDER BY table_schema, table_name"
        )
        tables = [(r[0], r[1]) for r in cur.fetchall()]
        for schema, v in tables:
            cur.execute(
                "SELECT column_name, data_type FROM information_schema.columns "
                f"WHERE table_schema = '{schema}' AND table_name = '{v}' ORDER BY ordinal_position"
            )
            fields = [
                SchemaFieldClass(fieldPath=c[0], type=_field_type(c[1]), nativeDataType=c[1])
                for c in cur.fetchall()
            ]
            urn = make_dataset_urn(platform="duckdb", name=v, env=ENV)
            aspects = [
                DatasetPropertiesClass(
                    name=v,
                    description=f"DuckDB table ({schema}) served over Arrow Flight SQL (GizmoSQL); "
                                "materialised from the lakeFS Parquet silver.",
                    customProperties={},
                ),
                GlobalTagsClass(tags=[TagAssociationClass(tag=make_tag_urn("default"))]),
                # lineage ← the parquet dataset of the same name (emitted by datasets_parquet)
                UpstreamLineageClass(upstreams=[UpstreamClass(
                    dataset=make_dataset_urn(platform="parquet", name=v, env=ENV),
                    type=DatasetLineageTypeClass.TRANSFORMED)]),
            ]
            if fields:
                aspects.insert(1, SchemaMetadataClass(
                    schemaName=v, platform="urn:li:dataPlatform:duckdb", version=0, hash="",
                    platformSchema=OtherSchemaClass(rawSchema=""), fields=fields))
            for aspect in aspects:
                emitter.emit(MetadataChangeProposalWrapper(entityUrn=urn, aspect=aspect))
            names.append(v)
    finally:
        conn.close()
    return len(names), names


def emit_timescaledb():
    """Custom-emit the TimescaleDB hypertables as DataHub Datasets (platform timescaledb) with schema
    (from information_schema) + lineage ← the source Dagster assets that write to them. Returns (count, names)."""
    import psycopg2

    conn = psycopg2.connect(
        host=os.environ.get("TIMESCALEDB_HOST", "timescaledb.data-mesh.svc.cluster.local"),
        port=int(os.environ.get("TIMESCALEDB_PORT", "5432")),
        dbname=os.environ.get("TIMESCALEDB_DB", "timeseries"),
        user=os.environ.get("TIMESCALEDB_USER", "weyland"),
        password=os.environ.get("TIMESCALEDB_PASSWORD", "weyland_dev_password"),
    )
    emitter = _gms_emitter()
    names = []
    lineage_map = {
        "eval_scores_ts": "eval_scores",
        "guardrail_verdicts_ts": "guardrail_verdicts",
        "dagster_run_durations": "runs",
        "unleash_feature_metrics": "client_metrics_env",
        "datahub_ingestion_runs": None,
    }
    # dataset-hydrated hypertables (data-store-mageddon): upstream is the silver parquet of the SAME name
    # (who_gho_adult_obesity ← parquet who_gho_adult_obesity), not a Postgres source table. Prefix-matched.
    dataset_hypertable_prefixes = ("who_gho_",)
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            AND table_name NOT LIKE '\\_\\_%'
        """)
        tables = [r[0] for r in cur.fetchall()]
        for t in tables:
            cur.execute(
                "SELECT column_name, data_type FROM information_schema.columns "
                f"WHERE table_schema = 'public' AND table_name = '{t}' ORDER BY ordinal_position"
            )
            fields = [
                SchemaFieldClass(fieldPath=c[0], type=_field_type(c[1]), nativeDataType=c[1])
                for c in cur.fetchall()
            ]
            urn = make_dataset_urn(platform="timescaledb", name=t, env=ENV)
            aspects = [
                DatasetPropertiesClass(
                    name=t,
                    description=f"TimescaleDB hypertable — time-series feed for the {t} data product.",
                    customProperties={"platform": "timescaledb"},
                ),
                GlobalTagsClass(tags=[TagAssociationClass(tag=make_tag_urn("timeseries"))]),
            ]
            if fields:
                aspects.insert(1, SchemaMetadataClass(
                    schemaName=t, platform="urn:li:dataPlatform:timescaledb", version=0, hash="",
                    platformSchema=OtherSchemaClass(rawSchema=""), fields=fields))
            src = lineage_map.get(t)
            if src:
                aspects.append(UpstreamLineageClass(upstreams=[UpstreamClass(
                    dataset=make_dataset_urn(platform="postgres", name=f"weyland.public.{src}", env=ENV),
                    type=DatasetLineageTypeClass.COPY)]))
            elif t.startswith(dataset_hypertable_prefixes):
                aspects.append(UpstreamLineageClass(upstreams=[UpstreamClass(
                    dataset=make_dataset_urn(platform="parquet", name=t, env=ENV),
                    type=DatasetLineageTypeClass.TRANSFORMED)]))
            for aspect in aspects:
                emitter.emit(MetadataChangeProposalWrapper(entityUrn=urn, aspect=aspect))
            names.append(t)
    finally:
        conn.close()
    return len(names), names


def emit_mysql():
    """Custom-emit the hydrated MySQL health tables as DataHub Datasets (platform mysql) with schema
    (information_schema) + lineage ← the silver Parquet they were loaded from (data-store-mageddon).
    Returns (count, names)."""
    import pymysql

    dbs = ["nhanes", "big_five", "who_gho", "cdc_physical_activity", "brfss", "nhis"]
    conn = pymysql.connect(
        host=os.environ.get("MYSQL_HOST", "mysql.data-mesh.svc.cluster.local"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_USER", "weyland"),
        password=os.environ.get("MYSQL_PASSWORD", "weyland_dev_password"),
    )
    emitter = _gms_emitter()
    names = []
    try:
        cur = conn.cursor()
        for db in dbs:
            cur.execute("SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema=%s AND table_type='BASE TABLE'", (db,))
            for (t,) in cur.fetchall():
                cur.execute("SELECT column_name, data_type FROM information_schema.columns "
                            "WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position", (db, t))
                fields = [SchemaFieldClass(fieldPath=c[0], type=_field_type(c[1]), nativeDataType=c[1])
                          for c in cur.fetchall()]
                name = f"{db}.{t}"
                urn = make_dataset_urn(platform="mysql", name=name, env=ENV)
                aspects = [
                    DatasetPropertiesClass(name=name,
                                           description=f"MySQL health table — {db} dataset, hydrated from silver Parquet.",
                                           customProperties={"platform": "mysql", "database": db}),
                    GlobalTagsClass(tags=[TagAssociationClass(tag=make_tag_urn("datasets_health"))]),
                ]
                if fields:
                    aspects.insert(1, SchemaMetadataClass(
                        schemaName=name, platform="urn:li:dataPlatform:mysql", version=0, hash="",
                        platformSchema=OtherSchemaClass(rawSchema=""), fields=fields))
                # lineage ← the folder-level parquet silver dataset (datasets.<db>) the loader read
                aspects.append(UpstreamLineageClass(upstreams=[UpstreamClass(
                    dataset=make_dataset_urn(platform="parquet", name=f"datasets.{db}", env=ENV),
                    type=DatasetLineageTypeClass.COPY)]))
                for aspect in aspects:
                    emitter.emit(MetadataChangeProposalWrapper(entityUrn=urn, aspect=aspect))
                names.append(name)
    finally:
        conn.close()
    return len(names), names


def emit_file_dataset(platform, table, location, arrow_schema, producer_asset, group="datasets") -> str:
    """Custom-emit a Dataset for a silver file format (Arrow/Lance) that has NO native DataHub connector.

    Emits dataset properties (format + S3 location), the COLUMN SCHEMA from the Arrow schema (so the
    schema tab populates), a group tag, and an UpstreamLineage edge to the producing Dagster asset
    (which datahub_emit catalogs on the dagster platform). Best-effort: callers wrap it so a DataHub
    hiccup never fails the underlying file write. Returns the dataset URN.
    """
    server = os.environ.get(
        "DATAHUB_GMS_URL", "http://datahub-datahub-gms.data-mesh.svc.cluster.local:8080"
    )
    emitter = DatahubRestEmitter(gms_server=server, token=os.environ.get("DATAHUB_GMS_TOKEN", ""))
    urn = make_dataset_urn(platform=platform, name=f"datasets.{table}", env=ENV)
    fields = [
        SchemaFieldClass(fieldPath=f.name, type=_field_type(f.type), nativeDataType=str(f.type))
        for f in arrow_schema
    ]
    aspects = [
        DatasetPropertiesClass(
            name=f"datasets.{table}",
            description=f"{platform} silver format of '{table}' at {location} "
            f"(B72; custom-emitted — no native DataHub connector for {platform}).",
            customProperties={"format": platform, "location": location, "dagster_group": group},
        ),
        SchemaMetadataClass(
            schemaName=f"datasets.{table}",
            platform=f"urn:li:dataPlatform:{platform}",
            version=0,
            hash="",
            platformSchema=OtherSchemaClass(rawSchema=""),
            fields=fields,
        ),
        GlobalTagsClass(tags=[TagAssociationClass(tag=make_tag_urn(group))]),
        UpstreamLineageClass(
            upstreams=[
                UpstreamClass(
                    dataset=make_dataset_urn(platform=PLATFORM, name=producer_asset, env=ENV),
                    type=DatasetLineageTypeClass.TRANSFORMED,
                )
            ]
        ),
    ]
    for aspect in aspects:
        emitter.emit(MetadataChangeProposalWrapper(entityUrn=urn, aspect=aspect))
    return urn


def emit() -> int:
    server = os.environ.get(
        "DATAHUB_GMS_URL",
        "http://datahub-datahub-gms.data-mesh.svc.cluster.local:8080",
    )
    token = os.environ.get("DATAHUB_GMS_TOKEN", "")
    emitter = DatahubRestEmitter(gms_server=server, token=token)
    emitter.test_connection()
    mcps = build_mcps()
    for mcp in mcps:
        emitter.emit(mcp)
    datasets = len({mcp.entityUrn for mcp in mcps})
    print(f"Emitted {len(mcps)} MCPs across {datasets} datasets to {server}")
    return datasets


if __name__ == "__main__":
    emit()
