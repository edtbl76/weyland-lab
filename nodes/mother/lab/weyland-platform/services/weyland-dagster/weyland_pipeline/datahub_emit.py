"""Custom DataHub emitter for the Dagster asset catalog + lineage.

Replaces the acryl-datahub-dagster-plugin sensor: its `datahub_sensor` is built on
Dagster's `run_status_sensor`, which is broken on Dagster 1.7.3+ (dagster#21526) and so
never emits on our 1.13.10 — confirmed: "Checking for new runs... skipped" every tick
even at zero run volume, indices stay at 0. This instead walks the asset graph directly
and pushes Dataset + UpstreamLineage to GMS via the REST emitter. No sensor, no cursor,
version-proof. Idempotent (DataHub upserts), so safe to run on a schedule or on demand.

Run standalone:  python -m weyland_pipeline.datahub_emit
"""
import os
from typing import Dict, List, Set

from dagster import AssetKey
from datahub.emitter.mce_builder import make_dataset_urn
from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.metadata.schema_classes import (
    DatasetLineageTypeClass,
    DatasetPropertiesClass,
    UpstreamClass,
    UpstreamLineageClass,
)

from weyland_pipeline.assets import all_assets

PLATFORM = "dagster"
ENV = "PROD"


def _name(key: AssetKey) -> str:
    return ".".join(key.path)


def _dep_map() -> Dict[AssetKey, Set[AssetKey]]:
    """asset_key -> set of upstream asset_keys, walking every AssetsDefinition.

    Degrades gracefully: if a def has no per-key deps (e.g. a SourceAsset), its keys are
    still recorded with empty upstreams so the dataset is cataloged without lineage.
    """
    deps: Dict[AssetKey, Set[AssetKey]] = {}
    for ad in all_assets:
        per_key = getattr(ad, "asset_deps", None)
        if per_key:
            for key, ups in per_key.items():
                deps.setdefault(key, set()).update(ups)
        else:
            for key in getattr(ad, "keys", []) or []:
                deps.setdefault(key, set())
    return deps


def build_mcps() -> List[MetadataChangeProposalWrapper]:
    deps = _dep_map()
    mcps: List[MetadataChangeProposalWrapper] = []
    for key, ups in deps.items():
        urn = make_dataset_urn(platform=PLATFORM, name=_name(key), env=ENV)
        mcps.append(
            MetadataChangeProposalWrapper(
                entityUrn=urn, aspect=DatasetPropertiesClass(name=_name(key))
            )
        )
        if ups:
            upstreams = [
                UpstreamClass(
                    dataset=make_dataset_urn(platform=PLATFORM, name=_name(u), env=ENV),
                    type=DatasetLineageTypeClass.TRANSFORMED,
                )
                for u in sorted(ups, key=_name)
            ]
            mcps.append(
                MetadataChangeProposalWrapper(
                    entityUrn=urn, aspect=UpstreamLineageClass(upstreams=upstreams)
                )
            )
    return mcps


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
