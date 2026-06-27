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
from datahub.emitter.mce_builder import make_dataset_urn, make_tag_urn
from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.metadata.schema_classes import (
    BooleanTypeClass,
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


def _gms_emitter() -> DatahubRestEmitter:
    server = os.environ.get("DATAHUB_GMS_URL", "http://datahub-datahub-gms.data-mesh.svc.cluster.local:8080")
    return DatahubRestEmitter(gms_server=server, token=os.environ.get("DATAHUB_GMS_TOKEN", ""))


def emit_qdrant():
    """Custom-emit one DataHub Dataset per Qdrant collection (props + a payload schema sampled from one
    point) with lineage ← qdrant_write. Returns (count, [collection names])."""
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
        for aspect in _store_aspects(name, "qdrant", "Qdrant vector collection (RAG dense backend).",
                                     fields, "qdrant_write", props):
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
            for aspect in _store_aspects(name, "weaviate", "Weaviate vector class (RAG dense backend).",
                                         fields, "weaviate_write"):
                emitter.emit(MetadataChangeProposalWrapper(entityUrn=urn, aspect=aspect))
            names.append(name)
    finally:
        client.close()
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
    """Custom-emit the GizmoSQL/DuckDB Flight SQL views as DataHub Datasets (platform duckdb) with schema
    (from information_schema) + lineage ← the parquet datasets they read. Connects to the live GizmoSQL
    server over Arrow Flight SQL (TLS, self-signed → skip verify). Returns (count, names)."""
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
        # our views live in the in-memory db's main schema; skip GizmoSQL's internal/system views.
        cur.execute("SELECT view_name FROM duckdb_views() WHERE schema_name = 'main' AND NOT internal")
        views = [r[0] for r in cur.fetchall() if not r[0].startswith(("_", "gizmosql"))]
        for v in views:
            cur.execute(
                "SELECT column_name, data_type FROM information_schema.columns "
                f"WHERE table_name = '{v}' ORDER BY ordinal_position"
            )
            fields = [
                SchemaFieldClass(fieldPath=c[0], type=_field_type(c[1]), nativeDataType=c[1])
                for c in cur.fetchall()
            ]
            urn = make_dataset_urn(platform="duckdb", name=v, env=ENV)
            aspects = [
                DatasetPropertiesClass(
                    name=v,
                    description="DuckDB view served over Arrow Flight SQL (GizmoSQL); reads the lakeFS Parquet.",
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
