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
from datahub.emitter.mce_builder import (
    make_chart_urn,
    make_dashboard_urn,
    make_dataset_urn,
    make_domain_urn,
    make_tag_urn,
)
from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.metadata.schema_classes import (
    AuditStampClass,
    BooleanTypeClass,
    ChangeAuditStampsClass,
    ChartInfoClass,
    DashboardInfoClass,
    DataProductAssociationClass,
    DataProductPropertiesClass,
    DatasetLineageTypeClass,
    DomainPropertiesClass,
    DomainsClass,
    DatasetPropertiesClass,
    EditableSchemaMetadataClass,
    EditableSchemaFieldInfoClass,
    GlobalTagsClass,
    GlossaryNodeInfoClass,
    GlossaryTermInfoClass,
    GlossaryTermsClass,
    GlossaryTermAssociationClass,
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

# Soda data-source name → Trino catalog.schema prefix. The Soda emitters (assertions/profiles/contracts) build the
# dataset URN from this, so scanning a gold schema attaches to the right entity instead of the hardcoded dbt marts.
_SODA_DS_SCHEMA = {
    "weyland": "iceberg.dbt",
    "weyland_health": "iceberg.datasets_health",
    "weyland_music": "iceberg.datasets_music",
}


def _soda_dataset_urn(datasource: str, table: str) -> str:
    prefix = _SODA_DS_SCHEMA.get(datasource, "iceberg.dbt")
    return make_dataset_urn(platform="trino", name=f"{prefix}.{table}", env=ENV)


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


# Domain definitions + assignment rules. Each cataloged asset (dataset/chart/dashboard) is assigned to the FIRST
# domain whose substring patterns match its (lowercased) URN — so order matters (specific → general; Platform is
# the catch-all last). Brand-neutral names (no "Method"). Row-level KB sub-structure (engineering/consulting/
# industry verticals) is NOT modelable as domains — it lives inside shared RAG datasets; that's a Data Product +
# glossary-term job (follow-up).
_DOMAINS = {
    "Music": "Music domain — datasets, dbt marts, Tier-2 stores, vectors, graph, Feast features, and BI.",
    "Health": "Health / wellness / personality domain — datasets, dbt marts, stores, Feast features, and BI.",
    "AIDLC Knowledge": "The AIDLC knowledge base — engineering-knowledge, consulting-tools, and industry-vertical repositories.",
    "Docs & RAG": "The platform documentation corpus and its retrieval stores (pgvector / OpenSearch / graph).",
    "Platform & Ops": "Operational, observability, and governance data — eval, guardrails, pipelines, CI, alerting, catalog.",
    "ML & Modeling": "Model registry and trained models.",
}
_DOMAIN_RULES = [
    ("Music", ("datasets_music", "mart_spotify_audio", "mart_genre_audio_profile", "mart_fma_genre_tree",
               "mart_artist_popularity", "track_audio_features", "spotify", "fma_", "lastfm", "musicbrainz",
               "gtzan", "audioset", "lp_musiccaps", "uci_year_prediction")),
    ("Health", ("datasets_health", "mart_state_health_trends", "mart_country_health", "mart_personality_by_country",
                "state_health_risk", "brfss", "nhanes", "nhis", "who_gho", "big_five", "cdc_physical", "usda",
                "open_food_facts")),
    ("AIDLC Knowledge", ("aidlc", ":entry", "entry,prod")),
    ("Docs & RAG", ("rag_documents", "rag_chunks", "weyland_chunks", "weylandchunk", "document,prod", "chunk,prod")),
    ("ML & Modeling", ("mlflow", "genre_classifier", "model_catalog", "registered_model", "model_version",
                       "latest_metrics")),
    ("Platform & Ops", ("eval", "guardrail", "dagster", "datahub", "unleash", "glitchtip", "sonarqube",
                        "timescaledb", "ai_session", "run_durations", "ingestion_runs", "event_log")),
]


def emit_domains():
    """Create the 6 DataHub domains + assign every cataloged dataset/chart/dashboard to one by URN pattern (first
    match wins). Runs each catalog cycle → new assets self-assign; brand-neutral (no 'Method'). Returns
    (n_domains, n_assigned)."""
    from datahub.ingestion.graph.client import DataHubGraph, DatahubClientConfig

    emitter = _gms_emitter()
    server = os.environ.get("DATAHUB_GMS_URL", "http://datahub-datahub-gms.data-mesh.svc.cluster.local:8080")
    token = os.environ.get("DATAHUB_GMS_TOKEN", "")

    durn = {}
    for name, desc in _DOMAINS.items():
        u = make_domain_urn(name.lower().replace(" & ", "-").replace(" ", "-"))
        durn[name] = u
        emitter.emit(MetadataChangeProposalWrapper(entityUrn=u, aspect=DomainPropertiesClass(name=name, description=desc)))

    graph = DataHubGraph(DatahubClientConfig(server=server, token=token))
    assigned = 0
    for etype in ("dataset", "chart", "dashboard"):
        for urn in graph.get_urns_by_filter(entity_types=[etype]):
            low = urn.lower()
            match = next((dname for dname, pats in _DOMAIN_RULES if any(p in low for p in pats)), None)
            # Fallback: everything unmatched (Grafana datasources, app-internal DBs, infra/observability data) is a
            # Platform & Ops concern → no dataset is left domainless. Business data still resolves its own domain above.
            emitter.emit(MetadataChangeProposalWrapper(
                entityUrn=urn, aspect=DomainsClass(domains=[durn[match or "Platform & Ops"]])))
            assigned += 1
    return len(_DOMAINS), assigned


# Data Products — mesh bundles: (name, domain, description, url patterns). Each bundles the cataloged assets whose
# URN matches a pattern, and is filed under its domain. The AIDLC KB is ONE product (its engineering/consulting/
# industry sub-structure is row-level inside shared RAG datasets — a glossary-term refinement, not separate assets).
_PRODUCTS = [
    ("Spotify Audio", "Music", "Track audio features + genre, the per-genre signature, and the Feast online view "
     "— the classifier's tested source of truth.", ("mart_spotify_audio", "mart_genre_audio_profile",
                                                     "track_audio_features")),
    ("Artist Popularity", "Music", "Last.fm plays + listeners per artist, joined to MusicBrainz.",
     ("mart_artist_popularity",)),
    ("Genre Taxonomy", "Music", "FMA genre hierarchy.", ("mart_fma_genre_tree",)),
    ("Chronic Health Trends", "Health", "BRFSS chronic-condition prevalence by state x year + the Feast online "
     "view.", ("mart_state_health_trends", "state_health_risk")),
    ("Global Health Indicators", "Health", "WHO GHO population-health indicators by country x year.",
     ("mart_country_health",)),
    ("Personality Profiles", "Health", "Big Five OCEAN traits by country.", ("mart_personality_by_country",)),
    ("Weyland Docs", "Docs & RAG", "The platform documentation retrieval corpus.",
     ("rag_documents", "rag_chunks", "weyland_chunks")),
    ("AIDLC Knowledge Base", "AIDLC Knowledge", "The AIDLC KB — engineering-knowledge, consulting-tools, and "
     "industry-vertical repositories (sub-structure lives in source_path / :Entry frontmatter).",
     ("aidlc", ":entry", "entry,prod")),
    ("Genre Classifier", "ML & Modeling", "The trained genre-classification model.", ("genre_classifier",)),
]


def emit_data_products():
    """Create the mesh Data Products + attach cataloged assets by URN pattern + file each under its domain.
    Returns (n_products, n_asset_links)."""
    import time

    from datahub.ingestion.graph.client import DataHubGraph, DatahubClientConfig

    emitter = _gms_emitter()
    server = os.environ.get("DATAHUB_GMS_URL", "http://datahub-datahub-gms.data-mesh.svc.cluster.local:8080")
    token = os.environ.get("DATAHUB_GMS_TOKEN", "")
    graph = DataHubGraph(DatahubClientConfig(server=server, token=token))
    now = int(time.time() * 1000)
    made = AuditStampClass(time=now, actor="urn:li:corpuser:datahub")

    urns = []
    for etype in ("dataset", "chart", "dashboard"):
        urns += list(graph.get_urns_by_filter(entity_types=[etype]))

    n_p = n_a = 0
    for pname, domain, desc, pats in _PRODUCTS:
        assets = [DataProductAssociationClass(destinationUrn=u, created=made)
                  for u in urns if any(p in u.lower() for p in pats)]
        purn = f"urn:li:dataProduct:{pname.lower().replace(' ', '-')}"
        emitter.emit(MetadataChangeProposalWrapper(entityUrn=purn, aspect=DataProductPropertiesClass(
            name=pname, description=desc, assets=assets)))
        emitter.emit(MetadataChangeProposalWrapper(entityUrn=purn, aspect=DomainsClass(
            domains=[make_domain_urn(domain.lower().replace(" & ", "-").replace(" ", "-"))])))
        n_p += 1
        n_a += len(assets)
    return n_p, n_a


def emit_glossary():
    """Publish the AIDLC KB taxonomy as a DataHub Business Glossary — the browsable answer to 'how do I find every
    industry vertical / consulting tool / delivery stage / engineering concept the KB is organized around?'. Domains
    and Data Products are asset-level; this sub-structure is ROW-level inside the shared RAG datasets, so it lives as
    glossary term groups + terms (independent of any single asset) instead. Nodes = the term groups (Industry
    Verticals, Consulting Tools, AIDLC Stages, Engineering Knowledge + its 12 tag-derived category sub-groups); terms
    = every leaf value with its REAL title + definition. Baked from .methodaidlc at build time into
    aidlc_glossary.GLOSSARY (the source files aren't in the dagster image). Idempotent — re-run adopts new/edited
    entries when the module is regenerated. Returns (n_nodes, n_terms)."""
    from weyland_pipeline.aidlc_glossary import GLOSSARY

    emitter = _gms_emitter()

    def _node_urn(nid):
        return f"urn:li:glossaryNode:{nid}"

    # Nodes first (GLOSSARY["nodes"] is already ordered parent-before-child), then terms reference them.
    n_nodes = 0
    for node in GLOSSARY["nodes"]:
        parent = _node_urn(node["parent"]) if node.get("parent") else None
        emitter.emit(MetadataChangeProposalWrapper(
            entityUrn=_node_urn(node["id"]),
            aspect=GlossaryNodeInfoClass(definition=node["definition"], name=node["name"], parentNode=parent)))
        n_nodes += 1

    n_terms = 0
    for term in GLOSSARY["terms"]:
        emitter.emit(MetadataChangeProposalWrapper(
            entityUrn=f"urn:li:glossaryTerm:{term['id']}",
            aspect=GlossaryTermInfoClass(definition=term["definition"], name=term["name"],
                                         termSource="INTERNAL", parentNode=_node_urn(term["parent"]))))
        n_terms += 1
    return n_nodes, n_terms


import re as _re

_STAT_SUFFIXES = ("_mean", "_std", "_sum", "_avg", "_min", "_max", "_count", "_median", "_p50", "_p95")

# Field-classification — a broad category assigned per field by name pattern. Drives BOTH a field tag AND (where no
# specific glossary term matched) a class-level field description, so no CLASSIFIABLE column is left blank. The
# truly domain-specific long tail (e.g. OFF's nutrition columns) stays honestly blank — meaning lives in the
# curated glossary vocabulary + the dbt marts, not in per-column filler.
_FIELD_CLASS_TAGS = {
    "identifier": "Field classification: identifier / key column.",
    "temporal": "Field classification: date / time / timestamp column.",
    "measure": "Field classification: numeric measure / metric.",
    "dimension": "Field classification: categorical dimension (group / filter).",
    "text": "Field classification: free-text / descriptive string.",
    "geo": "Field classification: geographic location.",
    "boolean": "Field classification: boolean flag.",
}
_FIELD_CLASS_DESC = {
    "identifier": "An identifier / key column.",
    "temporal": "A date, time, or timestamp column.",
    "measure": "A numeric measure or metric value.",
    "dimension": "A categorical dimension used to group or filter.",
    "text": "A free-text / descriptive string column.",
    "geo": "A geographic location column.",
    "boolean": "A boolean flag.",
}
_FC_EXACT = {
    "geo": {"geolocation", "latitude", "longitude", "lat", "lon", "lng", "coordinates", "geo"},
    "identifier": {"id", "gid", "uuid", "key", "code", "isbn", "ean", "upc", "seqn", "fdc_id", "mbid",
                   "track_id", "monitor_id", "organization_id", "project_id", "issue_id", "event_id",
                   "release_id", "span_id", "trace_id", "indicatorcode"},
    "temporal": {"timestamp", "date", "datetime", "time", "year", "month", "day", "week", "quarter",
                 "created", "modified", "updated", "timedim", "start_check"},
    "measure": {"value", "numericvalue", "data_value", "count", "sample_size", "response_time", "amount",
                "total", "score", "rate", "ratio", "pct", "percent", "quantity", "n_listeners", "total_plays"},
    "dimension": {"country", "state", "region", "city", "genre", "track_genre", "class", "topic", "question",
                  "category", "type", "kind", "status", "label", "group", "level", "sex", "gender", "age",
                  "race", "source", "datasource", "brand", "brands", "spatialdim", "spatialdimtype",
                  "timedimtype", "locationabbr", "locationdesc", "locationid", "parentlocation",
                  "classid", "topicid", "questionid"},
    "text": {"description", "url", "text", "body", "comment", "comments", "notes", "note", "title", "name",
             "message", "reason", "summary", "content", "abstract", "definition", "product_name"},
}


def _field_class(leaf):
    """Broad field category from a leaf column name — drives a define-once field tag + class-level description.
    Ordered: boolean prefix, then exact-set (geo/id/temporal/measure/dimension/text), then suffix rules for the
    long tail. First match wins; identifier `_id` is checked before the dimension/text suffixes."""
    l = leaf
    if l.startswith(("is_", "has_", "can_", "should_")):
        return "boolean"
    for cls, exact in _FC_EXACT.items():
        if l in exact:
            return cls
    if l.endswith(("_id", "_key", "_uuid", "_code", "_pk", "_fk", "_gid")):
        return "identifier"
    if (l.endswith(("_at", "_date", "_time", "_ts", "_timestamp", "_datetime", "_year", "_t"))
            or "timestamp" in l or "datetime" in l or l.startswith(("created", "modified", "updated", "last_"))):
        return "temporal"
    if l.endswith(("_pct", "_percent", "_mean", "_std", "_count", "_sum", "_avg", "_rate", "_ratio",
                   "_amount", "_total", "_score", "_n", "_num", "_value", "_min", "_max")):
        return "measure"
    if l.endswith(("_lat", "_lon", "_lng")):
        return "geo"
    if l.endswith(("_type", "_category", "_class", "_status", "_group", "_cat")):
        return "dimension"
    if l.endswith(("_name", "_text", "_desc", "_description", "_comment", "_note", "_title", "_url", "_message")):
        return "text"
    # domain-specific high-frequency patterns (from the unclassified-field audit)
    if l.startswith(("value_", "confidence")) or l.endswith(("_order", "_duration", "_bps", "_pps", "_ops", "_bytes")) or l == "duration":
        return "measure"
    if "timedimension" in l:
        return "temporal"
    if l.startswith("caption") or l in ("link", "editor", "track_composer", "abstract"):
        return "text"
    if l.endswith("_bucket") or l in ("parent", "labels", "release", "entity", "break_out", "pseudo_attribute"):
        return "dimension"
    if l == "guid":
        return "identifier"
    return None


def _type_class(field):
    """Fallback field class from the SCHEMA TYPE when the column name doesn't classify — Number → measure,
    Date/Time → temporal, Boolean → boolean, String → dimension. Type-derived tags are honest (a numeric field IS
    a measure). Used for TAGS only (not descriptions — those come from real source docs / the name classifier)."""
    t = getattr(getattr(field, "type", None), "type", None)
    n = type(t).__name__ if t is not None else ""
    if "Number" in n:
        return "measure"
    if "Date" in n or "Time" in n:
        return "temporal"
    if "Boolean" in n:
        return "boolean"
    if "String" in n:
        return "dimension"
    return None


def _field_leaf(field_path):
    """Leaf name from a DataHub v2 fieldPath, stripping '[version=…].[type=…]' annotations.
    e.g. '[version=2.0].[type=struct].[type=double].danceability' -> 'danceability'."""
    parts = [p for p in _re.sub(r"\[[^\]]*\]", "", field_path).split(".") if p]
    return (parts[-1] if parts else field_path).lower()


def _mesh_term_index():
    """{field-name pattern -> glossaryTerm urn} from mesh_vocabulary.TERMS. Exact-match keyed; the
    stat-suffix base (danceability_mean -> danceability) is resolved at match time, so 'entity0' and
    'entity0_credit' stay distinct terms (no greedy startswith)."""
    from weyland_pipeline.mesh_vocabulary import TERMS
    idx = {}
    for tid, _name, _parent, defn, attach in TERMS:
        for pat in attach:
            idx[pat.lower()] = (f"urn:li:glossaryTerm:{tid}", defn)
    return idx


def emit_mesh_glossary(attach=True):
    """Surface 1 — publish the authored Data-Mesh business vocabulary (mesh_vocabulary) as a second glossary root
    'Data Mesh', then (attach=True) walk every cataloged dataset's schema and attach each term to matching fields
    via 'define once, attach everywhere' — collapsing the 22k duplicated ambiguous fields. Field terms live in
    editableSchemaMetadata, which is a FULL-REPLACE aspect, so we READ-MERGE: existing field info + our term
    associations, re-emit. Idempotent. Returns (n_nodes, n_terms, n_fields_tagged, n_datasets_touched)."""
    import time

    from weyland_pipeline.mesh_vocabulary import NODES, TERMS

    emitter = _gms_emitter()

    def _nurn(nid):
        return f"urn:li:glossaryNode:{nid}"

    n_nodes = 0
    for nid, name, parent, defn in NODES:
        emitter.emit(MetadataChangeProposalWrapper(
            entityUrn=_nurn(nid),
            aspect=GlossaryNodeInfoClass(definition=defn, name=name, parentNode=_nurn(parent) if parent else None)))
        n_nodes += 1

    n_terms = 0
    for tid, name, parent, defn, _attach in TERMS:
        emitter.emit(MetadataChangeProposalWrapper(
            entityUrn=f"urn:li:glossaryTerm:{tid}",
            aspect=GlossaryTermInfoClass(definition=defn, name=name, termSource="INTERNAL",
                                         parentNode=_nurn(parent))))
        n_terms += 1

    if not attach:
        return n_nodes, n_terms, 0, 0

    from datahub.ingestion.graph.client import DataHubGraph, DatahubClientConfig
    server = os.environ.get("DATAHUB_GMS_URL", "http://datahub-datahub-gms.data-mesh.svc.cluster.local:8080")
    token = os.environ.get("DATAHUB_GMS_TOKEN", "")
    graph = DataHubGraph(DatahubClientConfig(server=server, token=token))

    idx = _mesh_term_index()
    now = int(time.time() * 1000)
    stamp = AuditStampClass(time=now, actor="urn:li:corpuser:datahub")

    def _match(leaf):
        if leaf in idx:
            return idx[leaf]
        for suf in _STAT_SUFFIXES:
            if leaf.endswith(suf) and leaf[: -len(suf)] in idx:
                return idx[leaf[: -len(suf)]]
        # PREFIX: a pattern matches a field starting with `<pattern>_` (data_value → data_value_unit/_footnote).
        # len>=4 guard so short patterns (id/op/gid) don't greedily swallow unrelated columns.
        for pat, val in idx.items():
            if len(pat) >= 4 and leaf.startswith(pat + "_"):
                return val
        return None

    n_fields = n_ds = 0
    for urn in graph.get_urns_by_filter(entity_types=["dataset"]):
        sm = graph.get_aspect(urn, SchemaMetadataClass)
        if not sm or not sm.fields:
            continue
        # per-field term/class matches. name_cls (from the column name) drives DESCRIPTION + tag; tag_cls falls
        # back to the SCHEMA TYPE for the tag only (so every typed field is classified) but never a description.
        want = {}  # fieldPath -> (term-tuple-or-None, name_cls-or-None, tag_cls-or-None)
        for f in sm.fields:
            leaf = _field_leaf(f.fieldPath)
            m = _match(leaf)
            name_cls = _field_class(leaf)
            tag_cls = name_cls or _type_class(f)
            if m or tag_cls:
                want[f.fieldPath] = (m, name_cls, tag_cls)
        if not want:
            continue
        # READ-MERGE the existing editable overlay so we don't clobber descriptions / other terms / other tags
        esm = graph.get_aspect(urn, EditableSchemaMetadataClass)
        infos = {i.fieldPath: i for i in (esm.editableSchemaFieldInfo if esm else [])}
        touched = 0
        for fp, (m, name_cls, tag_cls) in want.items():
            info = infos.get(fp) or EditableSchemaFieldInfoClass(fieldPath=fp)
            changed = False
            # description: the SPECIFIC glossary-term definition, else the name-class role description (NOT the
            # type fallback — a bare "measure" isn't a meaning). Never clobber a real one (source docs / dbt).
            new_desc = (m[1] if m else None) or (_FIELD_CLASS_DESC.get(name_cls) if name_cls else None)
            if new_desc and not info.description:
                info.description = new_desc
                changed = True
            if m:
                term_urn = m[0]
                existing = list(info.glossaryTerms.terms) if info.glossaryTerms else []
                if not any(a.urn == term_urn for a in existing):
                    existing.append(GlossaryTermAssociationClass(urn=term_urn))
                    info.glossaryTerms = GlossaryTermsClass(terms=existing, auditStamp=stamp)
                    changed = True
            if tag_cls:
                ctag = make_tag_urn(tag_cls)
                etags = list(info.globalTags.tags) if info.globalTags else []
                if not any(a.tag == ctag for a in etags):
                    etags.append(TagAssociationClass(tag=ctag))
                    info.globalTags = GlobalTagsClass(tags=etags)
                    changed = True
            infos[fp] = info
            if changed:
                touched += 1
        if not touched:
            continue
        emitter.emit(MetadataChangeProposalWrapper(
            entityUrn=urn,
            aspect=EditableSchemaMetadataClass(
                created=(esm.created if esm else stamp), lastModified=stamp,
                editableSchemaFieldInfo=list(infos.values()))))
        n_fields += touched
        n_ds += 1
    return n_nodes, n_terms, n_fields, n_ds


# Surface 2 — Structured Properties: typed, filterable facets. (qualifiedName, displayName, description,
# [(value, value-description)]). qualifiedName doubles as the URN id: urn:li:structuredProperty:<qualifiedName>.
_SP_DATASET_ET = "urn:li:entityType:datahub.dataset"
_SP_STRING = "urn:li:dataType:datahub.string"
_STRUCT_PROPS = {
    "weyland.data_layer": ("Data Layer", "Medallion / lakehouse layer of this dataset.", [
        ("raw", "Source data landed unmodified"), ("bronze", "Raw ingested layer"),
        ("silver", "Cleaned, conformed layer"), ("gold", "Business-level aggregates"),
        ("mart", "Curated, tested subject mart"), ("feature", "ML feature view / serving"),
        ("serving", "Retrieval / RAG serving corpus")]),
    "weyland.source_system": ("Source System", "Upstream system the data originates from.", [
        ("spotify", "Spotify audio features"), ("lastfm", "Last.fm plays/listeners"),
        ("musicbrainz", "MusicBrainz"), ("fma", "Free Music Archive"), ("gtzan", "GTZAN audio"),
        ("brfss", "CDC BRFSS survey"), ("who_gho", "WHO Global Health Observatory"),
        ("personality", "Big Five personality"), ("platform_docs", "Weyland docs / RAG"),
        ("aidlc_kb", "AIDLC knowledge base"), ("ai_dev", "AI-dev usage telemetry"),
        ("ops", "Platform / ops telemetry")]),
    "weyland.store_tier": ("Store Tier", "Which grid store physically holds this copy.", [
        ("lakehouse", "Iceberg / Trino / dbt / files"), ("tier2", "Tier-2 OLAP/doc/KV store"),
        ("vector", "Vector store"), ("graph", "Graph store"), ("streaming", "Kafka / Avro stream"),
        ("operational", "Operational RDBMS"), ("bi", "BI tool"), ("ml", "ML tracking / registry")]),
}

_STORE_TIER_BY_PLATFORM = {
    "trino": "lakehouse", "iceberg": "lakehouse", "dbt": "lakehouse", "s3": "lakehouse",
    "parquet": "lakehouse", "lakefs": "lakehouse", "duckdb": "lakehouse",
    "clickhouse": "tier2", "cassandra": "tier2", "mysql": "tier2", "mongodb": "tier2",
    "cockroachdb": "tier2", "opensearch": "tier2", "timescaledb": "tier2",
    "qdrant": "vector", "weaviate": "vector", "lance": "vector", "lancedb": "vector",
    "neo4j": "graph", "kafka": "streaming", "avro": "streaming", "arrow": "streaming",
    "postgres": "operational", "superset": "bi", "grafana": "bi", "mlflow": "ml",
}
# ordered (substring, source_system) — first match wins; specific before generic.
_SOURCE_RULES = [
    ("musicbrainz", "musicbrainz"), ("mbid", "musicbrainz"), ("spotify", "spotify"),
    ("lastfm", "lastfm"), ("last_fm", "lastfm"), ("gtzan", "gtzan"), ("fma", "fma"),
    ("brfss", "brfss"), ("state_health", "brfss"), ("health_trends", "brfss"),
    ("gho", "who_gho"), ("country_health", "who_gho"), ("personality", "personality"),
    ("ocean", "personality"), ("aidlc", "aidlc_kb"), ("ai_session", "ai_dev"), ("ai_dev", "ai_dev"),
    ("rag", "platform_docs"), ("weyland_chunks", "platform_docs"), ("docs", "platform_docs"),
    ("uptime", "ops"), ("kuma", "ops"), ("grafana", "ops"),
]


def _infer_layer(low):
    for key, val in (("mart_", "mart"), ("silver", "silver"), ("bronze", "bronze"), ("gold", "gold"),
                     ("feast", "feature"), ("feature", "feature"), ("chunk", "serving"), ("rag_", "serving")):
        if key in low:
            return val
    return None


def _infer_source(low):
    for sub, val in _SOURCE_RULES:
        if sub in low:
            return val
    return None


def emit_structured_properties():
    """Surface 2 — define the typed facets (data_layer / source_system / store_tier) and assign each cataloged
    dataset by URN pattern. Makes the catalog queryable (Domain=owner, Product=bundle, these=filter facets). Both
    the definitions and assignments come from git (UI-defined structured properties die on a DataHub rebuild).
    Returns (n_props_defined, n_datasets_assigned)."""
    from datahub.metadata.schema_classes import (
        PropertyValueClass, StructuredPropertiesClass, StructuredPropertyDefinitionClass,
        StructuredPropertyValueAssignmentClass)
    from datahub.ingestion.graph.client import DataHubGraph, DatahubClientConfig

    emitter = _gms_emitter()
    server = os.environ.get("DATAHUB_GMS_URL", "http://datahub-datahub-gms.data-mesh.svc.cluster.local:8080")
    token = os.environ.get("DATAHUB_GMS_TOKEN", "")

    n_props = 0
    for qname, (disp, desc, allowed) in _STRUCT_PROPS.items():
        emitter.emit(MetadataChangeProposalWrapper(
            entityUrn=f"urn:li:structuredProperty:{qname}",
            aspect=StructuredPropertyDefinitionClass(
                qualifiedName=qname, displayName=disp, description=desc, valueType=_SP_STRING,
                cardinality="SINGLE", entityTypes=[_SP_DATASET_ET],
                allowedValues=[PropertyValueClass(value=v, description=d) for v, d in allowed])))
        n_props += 1

    plat = lambda u: (_re.search(r"dataPlatform:([^,]+),", u) or [None, "?"])[1]
    graph = DataHubGraph(DatahubClientConfig(server=server, token=token))
    n_ds = 0
    for urn in graph.get_urns_by_filter(entity_types=["dataset"]):
        low = urn.lower()
        vals = {"weyland.data_layer": _infer_layer(low),
                "weyland.source_system": _infer_source(low),
                "weyland.store_tier": _STORE_TIER_BY_PLATFORM.get(plat(urn))}
        assigns = [StructuredPropertyValueAssignmentClass(propertyUrn=f"urn:li:structuredProperty:{q}", values=[v])
                   for q, v in vals.items() if v]
        if not assigns:
            continue
        emitter.emit(MetadataChangeProposalWrapper(entityUrn=urn, aspect=StructuredPropertiesClass(properties=assigns)))
        n_ds += 1
    return n_props, n_ds


# Surface 4 — Documentation Links: point each dataset OUT to its doc-site runbook (single source of truth on
# docs.weyland.lab; DataHub is the discovery layer, not a second copy of the prose). Base URL + pattern maps.
_DOCS_BASE = "https://docs.weyland.lab"
_PLATFORM_RUNBOOK = {
    "clickhouse": ("runbooks/datasets-hydration", "Tier-2 hydration runbook"),
    "cassandra": ("runbooks/datasets-hydration", "Tier-2 hydration runbook"),
    "mysql": ("runbooks/datasets-hydration", "Tier-2 hydration runbook"),
    "mongodb": ("runbooks/datasets-hydration", "Tier-2 hydration runbook"),
    "cockroachdb": ("runbooks/datasets-hydration", "Tier-2 hydration runbook"),
    "opensearch": ("runbooks/datasets-hydration", "Tier-2 hydration runbook"),
    "qdrant": ("runbooks/datasets-hydration", "Vector store hydration runbook"),
    "weaviate": ("runbooks/datasets-hydration", "Vector store hydration runbook"),
    "lance": ("runbooks/datasets-hydration", "Vector store hydration runbook"),
    "lancedb": ("runbooks/datasets-hydration", "Vector store hydration runbook"),
    "neo4j": ("runbooks/datasets-hydration", "Graph store hydration runbook"),
    "timescaledb": ("runbooks/timescaledb", "TimescaleDB runbook"),
    "duckdb": ("runbooks/gizmosql", "GizmoSQL / DuckDB runbook"),
    "trino": ("runbooks/trino", "Trino runbook"),
    "iceberg": ("runbooks/datasets-lake", "Lakehouse runbook"),
    "dbt": ("runbooks/dbt", "dbt transform runbook"),
    "s3": ("runbooks/storage-minio", "MinIO storage runbook"),
    "parquet": ("runbooks/datasets-lake", "Lakehouse runbook"),
    "lakefs": ("runbooks/datasets-lake", "lakeFS runbook"),
    "kafka": ("runbooks/streaming", "Streaming runbook"),
    "avro": ("runbooks/streaming", "Streaming runbook"),
    "arrow": ("runbooks/streaming", "Streaming runbook"),
    "mlflow": ("runbooks/mlflow", "MLflow runbook"),
    "superset": ("runbooks/superset", "Superset runbook"),
}
# ordered name-substring rules (first match adds its runbook, in addition to the platform one).
_NAME_RUNBOOK = [
    ("musicbrainz", ("runbooks/musicbrainz-postgres", "MusicBrainz Postgres runbook")),
    ("aidlc", ("runbooks/aidlc-kb-ingest", "AIDLC KB ingest runbook")),
    ("lightdash", ("runbooks/lightdash", "Lightdash runbook")),
    ("feast", ("runbooks/dbt", "dbt marts (Feast source) runbook")),
]
# appended to every dataset that matched at least one runbook — the mesh overview + the tools launchpad.
_COMMON_DOCS = [("data-mesh-guide", "Weyland Data Mesh guide"), ("tools", "Tools launchpad")]


def emit_docs_links():
    """Surface 4 — attach doc-site Links (institutionalMemory) to each dataset: its runbook(s) by platform/name +
    the mesh guide + the tools launchpad. DataHub becomes the discovery layer that points home to the canonical
    docs (docs.weyland.lab, git-backed) — no prose duplicated into DataHub. institutionalMemory is full-replace and
    we're its sole writer, so no merge. Returns (n_datasets_linked, n_links)."""
    import time

    from datahub.metadata.schema_classes import InstitutionalMemoryClass, InstitutionalMemoryMetadataClass
    from datahub.ingestion.graph.client import DataHubGraph, DatahubClientConfig

    emitter = _gms_emitter()
    server = os.environ.get("DATAHUB_GMS_URL", "http://datahub-datahub-gms.data-mesh.svc.cluster.local:8080")
    token = os.environ.get("DATAHUB_GMS_TOKEN", "")
    graph = DataHubGraph(DatahubClientConfig(server=server, token=token))
    stamp = AuditStampClass(time=int(time.time() * 1000), actor="urn:li:corpuser:datahub")
    plat = lambda u: (_re.search(r"dataPlatform:([^,]+),", u) or [None, "?"])[1]

    n_ds = n_links = 0
    for urn in graph.get_urns_by_filter(entity_types=["dataset"]):
        low = urn.lower()
        picks = []  # (path, label) — deduped by path below
        rb = _PLATFORM_RUNBOOK.get(plat(urn))
        if rb:
            picks.append(rb)
        for sub, nr in _NAME_RUNBOOK:
            if sub in low:
                picks.append(nr)
        if not picks:
            continue  # no runbook match → don't spam the dataset with only generic links
        picks.extend(_COMMON_DOCS)
        seen, elements = set(), []
        for path, label in picks:
            if path in seen:
                continue
            seen.add(path)
            elements.append(InstitutionalMemoryMetadataClass(
                url=f"{_DOCS_BASE}/{path}/", description=label, createStamp=stamp))
        emitter.emit(MetadataChangeProposalWrapper(entityUrn=urn, aspect=InstitutionalMemoryClass(elements=elements)))
        n_ds += 1
        n_links += len(elements)
    return n_ds, n_links


def emit_soda_assertions(scan_results: dict):
    """L5 Slice C → DataHub: turn a Soda scan-results JSON into per-check Assertions on the mart datasets, so the
    catalog's Assertions tab shows a green/red data-quality panel next to each mart's schema/glossary/lineage (the
    closest thing to a Soda UI without paying for Soda Cloud). Each check → a _NATIVE_ assertion (the check text IS
    the logic — no per-operator mapping) + an AssertionRunEvent carrying this run's pass/fail. Idempotent: the
    assertion URN is a stable hash of (table, check) so re-runs update the same assertion and append a run result.
    Called by soda_scan_op AFTER the scan; failures here are logged, never fatal (data quality > catalog cosmetics).
    """
    import hashlib
    import time
    from datahub.emitter.mce_builder import make_assertion_urn, make_schema_field_urn
    from datahub.metadata.schema_classes import (
        AssertionInfoClass,
        AssertionResultClass,
        AssertionResultTypeClass,
        AssertionRunEventClass,
        AssertionRunStatusClass,
        AssertionStdAggregationClass,
        AssertionStdOperatorClass,
        AssertionTypeClass,
        DatasetAssertionInfoClass,
        DatasetAssertionScopeClass,
    )
    emitter = _gms_emitter()
    ts = int(time.time() * 1000)
    run_id = f"soda-{ts}"
    n = 0
    for check in scan_results.get("checks", []):
        loc = check.get("location") or {}
        table = check.get("table") or loc.get("table")
        if not table:
            continue
        name = check.get("name") or check.get("definition") or "soda check"
        column = check.get("column")
        outcome = (check.get("outcome") or "").lower()
        mart_urn = _soda_dataset_urn(check.get("dataSource", "weyland"), table)
        assertion_urn = make_assertion_urn(hashlib.md5(f"{table}:{name}".encode()).hexdigest())
        info = AssertionInfoClass(
            type=AssertionTypeClass.DATASET,
            datasetAssertion=DatasetAssertionInfoClass(
                dataset=mart_urn,
                scope=DatasetAssertionScopeClass.DATASET_COLUMN if column else DatasetAssertionScopeClass.DATASET_ROWS,
                fields=[make_schema_field_urn(mart_urn, column)] if column else [],
                aggregation=AssertionStdAggregationClass._NATIVE_,
                operator=AssertionStdOperatorClass._NATIVE_,
                nativeType=name,
            ),
            customProperties={"source": "soda", "check": name},
            description=name,
        )
        emitter.emit(MetadataChangeProposalWrapper(entityUrn=assertion_urn, aspect=info))
        result_type = AssertionResultTypeClass.SUCCESS if outcome == "pass" else AssertionResultTypeClass.FAILURE
        emitter.emit(MetadataChangeProposalWrapper(
            entityUrn=assertion_urn,
            aspect=AssertionRunEventClass(
                timestampMillis=ts,
                runId=run_id,
                assertionUrn=assertion_urn,
                asserteeUrn=mart_urn,
                status=AssertionRunStatusClass.COMPLETE,
                result=AssertionResultClass(type=result_type),
            ),
        ))
        n += 1
    return n


def emit_soda_profiles(scan_results: dict):
    """L5 Slice C → DataHub **Stats**: reuse the numbers Soda already computed (`metrics` in the -srf JSON) as a
    `DatasetProfile` per mart — rowCount + per-column nullCount/min/max — so the greyed-out Stats tab populates
    without a separate profiling ingestion. Soda metric identities are `metric-Soda Core CLI-weyland-<table>-<col>-
    <metricName>` (table/col/metric names are underscore-delimited, so `-` cleanly separates the three parts)."""
    import time
    from datahub.metadata.schema_classes import DatasetFieldProfileClass, DatasetProfileClass
    emitter = _gms_emitter()
    ts = int(time.time() * 1000)
    prefix = "metric-Soda Core CLI-"
    tables: dict = {}
    for m in scan_results.get("metrics", []):
        ident = m.get("identity", "")
        if not ident.startswith(prefix):
            continue
        body = ident[len(prefix):]        # <datasource>-<table>-<col>-<metric>
        ds = body.split("-")[0]           # datasource name (underscore-safe, no hyphens)
        rest = body[len(ds) + 1:]         # <table>-<col>-<metric>
        mn, val = m.get("metricName"), m.get("value")
        if val is None:
            continue
        table = rest.split("-")[0]
        if rest == f"{table}-{mn}":
            column = None
        elif rest.endswith(f"-{mn}"):
            column = rest[len(table) + 1: -(len(mn) + 1)]
        else:
            column = None  # e.g. duplicate_count-<hash> — table-level, skip for field profiles
        t = tables.setdefault((ds, table), {"rowCount": None, "fields": {}})
        if mn == "row_count" and column is None:
            t["rowCount"] = int(val)
        elif column:
            f = t["fields"].setdefault(column, {})
            if mn == "missing_count":
                f["nullCount"] = int(val)
            elif mn == "min":
                f["min"] = str(val)
            elif mn == "max":
                f["max"] = str(val)
    n = 0
    for (ds, table), t in tables.items():
        mart_urn = _soda_dataset_urn(ds, table)
        fps = []
        for col, f in t["fields"].items():
            null_prop = None
            if f.get("nullCount") is not None and t["rowCount"]:
                null_prop = round(f["nullCount"] / t["rowCount"], 4)
            fps.append(DatasetFieldProfileClass(
                fieldPath=col, nullCount=f.get("nullCount"), nullProportion=null_prop,
                min=f.get("min"), max=f.get("max"),
            ))
        emitter.emit(MetadataChangeProposalWrapper(entityUrn=mart_urn, aspect=DatasetProfileClass(
            timestampMillis=ts, rowCount=t["rowCount"],
            columnCount=len(t["fields"]) or None, fieldProfiles=fps or None,
        )))
        n += 1
    return n


def emit_data_contracts(scan_results: dict):
    """L5 Slice C → DataHub **Data Contract**: one `DataContract` per mart that bundles its Soda checks as the
    dataQuality contract — referencing the SAME assertion URNs `emit_soda_assertions` mints (stable md5(table:check)).
    The mart *is* the contract: publishing it means those checks must hold. Populates the mart's Data Contract tab."""
    import hashlib
    from datahub.emitter.mce_builder import make_assertion_urn
    from datahub.metadata.schema_classes import (
        DataContractPropertiesClass,
        DataContractStatusClass,
        DataQualityContractClass,
    )
    emitter = _gms_emitter()
    by_table: dict = {}
    for check in scan_results.get("checks", []):
        table = check.get("table") or (check.get("location") or {}).get("table")
        if not table:
            continue
        name = check.get("name") or check.get("definition") or "soda check"
        aurn = make_assertion_urn(hashlib.md5(f"{table}:{name}".encode()).hexdigest())
        by_table.setdefault((check.get("dataSource", "weyland"), table), []).append(aurn)
    n = 0
    for (ds, table), aurns in by_table.items():
        mart_urn = _soda_dataset_urn(ds, table)
        dc_urn = f"urn:li:dataContract:{hashlib.md5(table.encode()).hexdigest()}"
        emitter.emit(MetadataChangeProposalWrapper(entityUrn=dc_urn, aspect=DataContractPropertiesClass(
            entity=mart_urn,
            dataQuality=[DataQualityContractClass(assertion=a) for a in aurns],
        )))
        emitter.emit(MetadataChangeProposalWrapper(
            entityUrn=dc_urn, aspect=DataContractStatusClass(state="ACTIVE")))
        n += 1
    return n


_TAGS = {
    "bronze": "Medallion **bronze** layer — raw landed data (as ingested, unmodified).",
    "silver": "Medallion **silver** layer — cleaned, conformed, type-cast data.",
    "gold": "Medallion **gold** layer — curated, query-ready domain tables (the dbt sources).",
    "mart": "A dbt **mart** — the tested, published contract tables (`iceberg.dbt.mart_*`).",
    "feast": "Materialized into the **Feast** feature store (online Valkey + offline Postgres).",
}


def emit_tags():
    """#1 tag layer — MATERIALIZE the full data-mesh tag vocabulary as first-class Tag entities (name + description):
    medallion layers + feast, the store-tier + source-system values (mirrored from the structured-property
    vocabulary so tag == facet), and the field-classification tags. Applied to datasets by emit_tag_assignments and
    to fields by emit_mesh_glossary. Returns the count of tag entities defined."""
    from datahub.metadata.schema_classes import TagPropertiesClass
    emitter = _gms_emitter()
    tags = dict(_TAGS)                       # medallion + feast
    for _q, (_disp, _desc, allowed) in _STRUCT_PROPS.items():   # layer / source / store-tier values → tags
        for val, vdesc in allowed:
            tags.setdefault(val, vdesc)
    tags.update(_FIELD_CLASS_TAGS)           # identifier / temporal / measure
    for name, desc in tags.items():
        emitter.emit(MetadataChangeProposalWrapper(
            entityUrn=make_tag_urn(name), aspect=TagPropertiesClass(name=name, description=desc)))
    return len(tags)


def emit_tag_assignments():
    """#1/#3 tag layer — apply DATASET tags cluster-wide by URN pattern (READ-MERGE — never clobbers existing
    default/group tags): the medallion **layer** (_infer_layer; Tier-2/vector/graph copies default to silver), the
    **store-tier** (_STORE_TIER_BY_PLATFORM by platform), and the **source-system** (_infer_source). Same
    classifiers as the structured-property facets, surfaced as filterable tags. Returns datasets tagged."""
    from datahub.ingestion.graph.client import DataHubGraph, DatahubClientConfig
    from datahub.metadata.schema_classes import GlobalTagsClass
    emitter = _gms_emitter()
    server = os.environ.get("DATAHUB_GMS_URL", "http://datahub-datahub-gms.data-mesh.svc.cluster.local:8080")
    token = os.environ.get("DATAHUB_GMS_TOKEN", "")
    graph = DataHubGraph(DatahubClientConfig(server=server, token=token))
    plat = lambda u: (_re.search(r"dataPlatform:([^,]+),", u) or [None, "?"])[1]
    n = 0
    for urn in graph.get_urns_by_filter(entity_types=["dataset"]):
        low = urn.lower()
        tier = _STORE_TIER_BY_PLATFORM.get(plat(urn))
        layer = _infer_layer(low) or ("silver" if tier in ("tier2", "vector", "graph") else None)
        source = _infer_source(low)
        want = {t for t in (layer, tier, source) if t}
        if not want:
            continue
        gt = graph.get_aspect(urn, GlobalTagsClass)
        merged = list(gt.tags) if gt and gt.tags else []
        have = {a.tag for a in merged}
        added = False
        for t in want:
            tu = make_tag_urn(t)
            if tu not in have:
                merged.append(TagAssociationClass(tag=tu))
                added = True
        if added:
            emitter.emit(MetadataChangeProposalWrapper(entityUrn=urn, aspect=GlobalTagsClass(tags=merged)))
            n += 1
    return n


def emit_field_docs():
    """#3 real field meaning — attach per-column descriptions transcribed from each dataset's SOURCE field
    dictionary (datasets_field_docs.FIELD_DOCS). Match a dataset by name substring, describe each field by its
    exact column doc or a suffix rule (`*_100g` etc.), and attach to EVERY store copy (read-merge, never clobbers
    an existing description). This is the meaning that pattern-classification can't give the domain-specific
    columns. Returns (datasets touched, fields described)."""
    import time

    from datahub.ingestion.graph.client import DataHubGraph, DatahubClientConfig
    from weyland_pipeline.datasets_field_docs import (
        FIELD_DOCS,
        FIELD_DOCS_PREFIX,
        FIELD_DOCS_SUFFIX,
        GLOBAL_COLS,
    )

    emitter = _gms_emitter()
    server = os.environ.get("DATAHUB_GMS_URL", "http://datahub-datahub-gms.data-mesh.svc.cluster.local:8080")
    token = os.environ.get("DATAHUB_GMS_TOKEN", "")
    graph = DataHubGraph(DatahubClientConfig(server=server, token=token))
    stamp = AuditStampClass(time=int(time.time() * 1000), actor="urn:li:corpuser:datahub")
    n_ds = n_f = 0
    for urn in graph.get_urns_by_filter(entity_types=["dataset"]):
        low = urn.lower()
        key = next((k for k in FIELD_DOCS if k in low), None)
        if not key:
            continue
        exact = {**GLOBAL_COLS, **FIELD_DOCS[key]}
        prefix = sorted(FIELD_DOCS_PREFIX.get(key, {}).items(), key=lambda kv: -len(kv[0]))
        suffix = FIELD_DOCS_SUFFIX.get(key, {})
        sm = graph.get_aspect(urn, SchemaMetadataClass)
        if not sm or not sm.fields:
            continue
        esm = graph.get_aspect(urn, EditableSchemaMetadataClass)
        infos = {i.fieldPath: i for i in (esm.editableSchemaFieldInfo if esm else [])}
        touched = 0
        for f in sm.fields:
            leaf = _field_leaf(f.fieldPath)
            lu = leaf.replace(" ", "_")
            desc = (exact.get(leaf) or exact.get(lu)
                    or next((d for p, d in prefix if lu.startswith(p)), None)
                    or next((d for suf, d in suffix.items() if leaf.endswith(suf)), None))
            if not desc:
                continue
            info = infos.get(f.fieldPath) or EditableSchemaFieldInfoClass(fieldPath=f.fieldPath)
            if not info.description:
                info.description = desc
                infos[f.fieldPath] = info
                touched += 1
        if touched:
            emitter.emit(MetadataChangeProposalWrapper(entityUrn=urn, aspect=EditableSchemaMetadataClass(
                created=(esm.created if esm else stamp), lastModified=stamp,
                editableSchemaFieldInfo=list(infos.values()))))
            n_ds += 1
            n_f += touched
    return n_ds, n_f


def emit_ownership():
    """#9 ownership fix — solo lab: the `weyland` group is Technical Owner of every dataset. Creates the CorpGroup
    entity, then stamps Ownership across all datasets so the 'No owners yet' governance gap clears cluster-wide."""
    from datahub.ingestion.graph.client import DataHubGraph, DatahubClientConfig
    from datahub.metadata.schema_classes import (
        CorpGroupInfoClass,
        OwnerClass,
        OwnershipClass,
        OwnershipTypeClass,
    )
    emitter = _gms_emitter()
    server = os.environ.get("DATAHUB_GMS_URL", "http://datahub-datahub-gms.data-mesh.svc.cluster.local:8080")
    token = os.environ.get("DATAHUB_GMS_TOKEN", "")
    group_urn = "urn:li:corpGroup:weyland"
    emitter.emit(MetadataChangeProposalWrapper(entityUrn=group_urn, aspect=CorpGroupInfoClass(
        admins=[], members=[], groups=[], displayName="Weyland", description="Weyland lab data owners.")))
    ownership = OwnershipClass(owners=[OwnerClass(owner=group_urn, type=OwnershipTypeClass.TECHNICAL_OWNER)])
    graph = DataHubGraph(DatahubClientConfig(server=server, token=token))
    n = 0
    for urn in graph.get_urns_by_filter(entity_types=["dataset"]):
        emitter.emit(MetadataChangeProposalWrapper(entityUrn=urn, aspect=ownership))
        n += 1
    return n


_MART_QUERIES = {
    "mart_spotify_audio": "-- Genre audio signature: mean danceability/energy per genre\nSELECT track_genre, count(*) AS tracks, avg(danceability) AS avg_danceability, avg(energy) AS avg_energy\nFROM iceberg.dbt.mart_spotify_audio\nGROUP BY track_genre\nORDER BY avg_danceability DESC",
    "mart_genre_audio_profile": "-- Most danceable genres by their profile\nSELECT track_genre, n_tracks, danceability_mean, energy_mean, valence_mean\nFROM iceberg.dbt.mart_genre_audio_profile\nORDER BY danceability_mean DESC\nLIMIT 20",
    "mart_fma_genre_tree": "-- Top-level FMA genres and their children count\nSELECT parent_title, count(*) AS subgenres\nFROM iceberg.dbt.mart_fma_genre_tree\nWHERE parent_title IS NOT NULL\nGROUP BY parent_title\nORDER BY subgenres DESC",
    "mart_artist_popularity": "-- Most-played Last.fm artists\nSELECT artist_name, total_plays, n_listeners\nFROM iceberg.dbt.mart_artist_popularity\nORDER BY total_plays DESC\nLIMIT 25",
    "mart_state_health_trends": "-- Diabetes prevalence trend for the latest year\nSELECT state, year, diabetes_pct, depression_pct\nFROM iceberg.dbt.mart_state_health_trends\nWHERE year = (SELECT max(year) FROM iceberg.dbt.mart_state_health_trends)\nORDER BY diabetes_pct DESC",
    "mart_country_health": "-- Life-expectancy leaders (both-sexes total)\nSELECT country, year, life_expectancy, healthy_life_expectancy, diabetes_prevalence\nFROM iceberg.dbt.mart_country_health\nWHERE year = (SELECT max(year) FROM iceberg.dbt.mart_country_health)\nORDER BY life_expectancy DESC\nLIMIT 25",
    "mart_personality_by_country": "-- OCEAN openness vs extraversion by country\nSELECT country, n_respondents, openness, extraversion, conscientiousness\nFROM iceberg.dbt.mart_personality_by_country\nORDER BY openness DESC\nLIMIT 25",
}


def emit_queries():
    """#4 queries fix — git-emit one canonical example Query per mart (statement + subject = the mart) so the
    empty Queries tab shows a runnable, reproducible starting query instead of 'No highlighted queries yet'."""
    import hashlib
    import time
    from datahub.metadata.schema_classes import (
        QueryLanguageClass,
        QueryPropertiesClass,
        QuerySourceClass,
        QueryStatementClass,
        QuerySubjectClass,
        QuerySubjectsClass,
    )
    emitter = _gms_emitter()
    stamp = AuditStampClass(time=int(time.time() * 1000), actor="urn:li:corpuser:__datahub_system")
    n = 0
    for mart, sql in _MART_QUERIES.items():
        mart_urn = make_dataset_urn(platform="trino", name=f"iceberg.dbt.{mart}", env=ENV)
        q_urn = f"urn:li:query:{hashlib.md5(('example:' + mart).encode()).hexdigest()}"
        emitter.emit(MetadataChangeProposalWrapper(entityUrn=q_urn, aspect=QueryPropertiesClass(
            statement=QueryStatementClass(value=sql, language=QueryLanguageClass.SQL),
            source=QuerySourceClass.MANUAL,
            name=f"Example — {mart}",
            description="Canonical starter query (git-emitted).",
            created=stamp, lastModified=stamp,
        )))
        emitter.emit(MetadataChangeProposalWrapper(
            entityUrn=q_urn, aspect=QuerySubjectsClass(subjects=[QuerySubjectClass(entity=mart_urn)])))
        n += 1
    return n


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


def _emit_profile(emitter, urn, row_count, column_count=None):
    """B80 Stats-wide: emit a rowCount-only DatasetProfile (timeseries aspect) so a custom-emitted store dataset's
    Stats tab populates — the cheap, table-level equivalent of the ingestion profiling we enabled for the recipe
    stores (no per-column scans). Callers guard the count fetch; a None row_count is a no-op."""
    if row_count is None:
        return 0
    import time
    from datahub.metadata.schema_classes import DatasetProfileClass
    emitter.emit(MetadataChangeProposalWrapper(entityUrn=urn, aspect=DatasetProfileClass(
        timestampMillis=int(time.time() * 1000), rowCount=int(row_count), columnCount=column_count)))
    return 1


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
        props, fields, rows = {}, [], None
        try:
            info = client.get_collection(name)
            rows = info.points_count
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
        _emit_profile(emitter, urn, rows, len(fields) or None)
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
            rows = None
            try:
                rows = client.collections.get(name).aggregate.over_all(total_count=True).total_count
            except Exception:  # noqa: BLE001
                pass
            _emit_profile(emitter, urn, rows, len(fields) or None)
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
            tbl = db.open_table(table)
            schema = tbl.schema
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
            rows = None
            try:
                rows = tbl.count_rows()
            except Exception:  # noqa: BLE001
                pass
            _emit_profile(emitter, urn, rows, len(fields) or None)
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
        rows = None
        try:
            with urllib.request.urlopen(f"{base}/{idx}/_count", timeout=30) as r:
                rows = json.load(r).get("count")
        except Exception:  # noqa: BLE001
            pass
        _emit_profile(emitter, urn, rows, len(fields) or None)
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
            rows = None
            try:
                cur.execute(f'SELECT count(*) FROM "{schema}"."{v}"')
                rows = cur.fetchone()[0]
            except Exception:  # noqa: BLE001
                pass
            _emit_profile(emitter, urn, rows, len(fields) or None)
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
            rows = None
            try:
                cur.execute(f"""SELECT approximate_row_count('public."{t}"')""")
                rows = cur.fetchone()[0]
            except Exception:  # noqa: BLE001
                conn.rollback()   # a failed query aborts the psycopg2 txn — reset so later SELECTs still work
            _emit_profile(emitter, urn, rows, len(fields) or None)
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
                rows = None
                try:
                    cur.execute(f"SELECT count(*) FROM `{db}`.`{t}`")
                    rows = cur.fetchone()[0]
                except Exception:  # noqa: BLE001
                    pass
                _emit_profile(emitter, urn, rows, len(fields) or None)
                names.append(name)
    finally:
        conn.close()
    return len(names), names


def emit_cockroachdb_profiles():
    """B80 Stats-wide: the DataHub cockroachdb ingestion profiler emits no DatasetProfile (0/9 despite `profiling`
    enabled), so custom-emit rowCount profiles onto the cockroach datasets it DID catalog. Cockroach is db-per-
    dataset (brfss, nhis); the ingestion URN name is `<db>.<table>`. Connect per database (information_schema is
    current-db-scoped), count each public base table, emit a profile on the matching URN. Insecure single-node →
    user root, sslmode disable (Cockroach is pg-WIRE, so psycopg2 connects fine). Returns profiles emitted."""
    import psycopg2
    emitter = _gms_emitter()
    host = os.environ.get("COCKROACHDB_HOST", "cockroachdb.data-mesh.svc.cluster.local")
    port = int(os.environ.get("COCKROACHDB_PORT", "26257"))
    user = os.environ.get("COCKROACHDB_USER", "root")
    n = 0
    for db in ("brfss", "nhis"):
        try:
            conn = psycopg2.connect(host=host, port=port, dbname=db, user=user, sslmode="disable")
        except Exception:  # noqa: BLE001
            continue
        try:
            cur = conn.cursor()
            cur.execute("SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema='public' AND table_type='BASE TABLE'")
            for (t,) in cur.fetchall():
                urn = make_dataset_urn(platform="cockroachdb", name=f"{db}.{t}", env=ENV)
                rows = None
                try:
                    cur.execute(f'SELECT count(*) FROM public."{t}"')
                    rows = cur.fetchone()[0]
                except Exception:  # noqa: BLE001
                    conn.rollback()
                n += _emit_profile(emitter, urn, rows)
        finally:
            conn.close()
    return n


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
