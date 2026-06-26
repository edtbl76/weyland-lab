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


def _field_type(arrow_type) -> SchemaFieldDataTypeClass:
    s = str(arrow_type)
    if s.startswith(("int", "uint", "double", "float", "decimal", "halffloat")):
        return SchemaFieldDataTypeClass(type=NumberTypeClass())
    if s == "bool":
        return SchemaFieldDataTypeClass(type=BooleanTypeClass())
    return SchemaFieldDataTypeClass(type=StringTypeClass())


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
