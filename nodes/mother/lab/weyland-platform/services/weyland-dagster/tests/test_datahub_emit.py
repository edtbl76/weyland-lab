"""Tests for the DataHub metadata emitter's payload-building logic (the 3k-line ``datahub_emit``).

Every dataset in the estate is catalogued by these builders. If they mis-map a field's category, drop lineage, or
attach an aspect to the wrong URN, the DataHub catalog is silently wrong — the classic "it ran, so it's fine" trap,
because a bad emit still returns cleanly. So we assert the REAL aspects built (via the real acryl-datahub SDK), not
that a mock was called:
  * ``_field_class`` — the field-category classifier (cc22) that drives every field's tag + description.
  * ``build_mcps`` — the asset → (DatasetProperties / GlobalTags / UpstreamLineage) builder, the core of the emit.

The live DataHub REST round-trip is validated in the running system; this pins the decision logic underneath it.
"""
import pytest


# ── _field_class: the field-category classifier ──────────────────────────────────────────────────────
@pytest.mark.parametrize("leaf", ["is_active", "has_children", "can_edit", "should_retry"])
def test_field_class_boolean_prefixes(datahub_emit, leaf):
    assert datahub_emit._field_class(leaf) == "boolean"


@pytest.mark.parametrize("leaf,cls", [
    ("latitude", "geo"), ("longitude", "geo"), ("coordinates", "geo"),
    ("uuid", "identifier"), ("mbid", "identifier"), ("track_id", "identifier"),
    ("timestamp", "temporal"), ("year", "temporal"), ("created", "temporal"),
    ("score", "measure"), ("total_plays", "measure"), ("response_time", "measure"),
    ("country", "dimension"), ("genre", "dimension"), ("status", "dimension"),
])
def test_field_class_exact_set_wins(datahub_emit, leaf, cls):
    assert datahub_emit._field_class(leaf) == cls


@pytest.mark.parametrize("leaf,cls", [
    ("user_id", "identifier"), ("row_key", "identifier"), ("session_uuid", "identifier"), ("iso_code", "identifier"),
    ("created_at", "temporal"), ("event_date", "temporal"), ("load_ts", "temporal"), ("birth_year", "temporal"),
    ("win_pct", "measure"), ("play_count", "measure"), ("order_amount", "measure"), ("final_score", "measure"),
    ("point_lat", "geo"), ("point_lon", "geo"), ("origin_lng", "geo"),
    ("event_type", "dimension"), ("order_status", "dimension"), ("user_group", "dimension"),
    ("first_name", "text"), ("body_text", "text"), ("long_description", "text"), ("page_url", "text"),
])
def test_field_class_suffix_rules(datahub_emit, leaf, cls):
    assert datahub_emit._field_class(leaf) == cls


def test_field_class_identifier_suffix_beats_dimension(datahub_emit):
    # docstring contract: `_id` is checked BEFORE the dimension/text suffixes, so a *_id wins even when the stem
    # (category) looks like a dimension. Get this order wrong and every foreign key is mis-tagged as a dimension.
    assert datahub_emit._field_class("category_id") == "identifier"
    assert datahub_emit._field_class("status_key") == "identifier"


def test_field_class_prefix_beats_suffix(datahub_emit):
    # a boolean prefix is tested first — "is_...": boolean even if the tail would otherwise be a measure/text
    assert datahub_emit._field_class("is_total") == "boolean"


# ── build_mcps: asset info → MetadataChangeProposals ──────────────────────────────────────────────────
class _Key:
    """A stand-in for dagster's AssetKey — build_mcps only needs `.path` (see _name = ".".join(key.path))."""
    def __init__(self, *path):
        self.path = list(path)

    def __hash__(self):
        return hash(tuple(self.path))

    def __eq__(self, other):
        return isinstance(other, _Key) and self.path == other.path


def _info(datahub_emit, deps=frozenset(), description=None, group=None):
    return datahub_emit.AssetInfo(deps=set(deps), description=description, group=group)


def test_build_mcps_emits_dataset_properties_with_group_property(datahub_emit, monkeypatch):
    from datahub.metadata.schema_classes import DatasetPropertiesClass

    key = _Key("music", "fma_tracks")
    monkeypatch.setattr(datahub_emit, "_asset_info",
                        lambda: {key: _info(datahub_emit, description="FMA audio tracks", group="music")})
    mcps = datahub_emit.build_mcps()
    props = [m for m in mcps if isinstance(m.aspect, DatasetPropertiesClass)]
    assert len(props) == 1
    assert props[0].aspect.name == "music.fma_tracks"
    assert props[0].aspect.description == "FMA audio tracks"
    assert props[0].aspect.customProperties.get("dagster_group") == "music"
    assert "fma_tracks" in props[0].entityUrn


def test_build_mcps_tags_the_group(datahub_emit, monkeypatch):
    from datahub.metadata.schema_classes import GlobalTagsClass

    key = _Key("health", "nhanes")
    monkeypatch.setattr(datahub_emit, "_asset_info",
                        lambda: {key: _info(datahub_emit, description="d", group="health")})
    tags = [m for m in datahub_emit.build_mcps() if isinstance(m.aspect, GlobalTagsClass)]
    assert len(tags) == 1
    assert any("health" in t.tag for t in tags[0].aspect.tags)


def test_build_mcps_no_group_means_no_tag_and_empty_props(datahub_emit, monkeypatch):
    from datahub.metadata.schema_classes import DatasetPropertiesClass, GlobalTagsClass

    key = _Key("misc", "loose")
    monkeypatch.setattr(datahub_emit, "_asset_info",
                        lambda: {key: _info(datahub_emit, description="d", group=None)})
    mcps = datahub_emit.build_mcps()
    assert not any(isinstance(m.aspect, GlobalTagsClass) for m in mcps)          # no group → no tag aspect
    props = [m for m in mcps if isinstance(m.aspect, DatasetPropertiesClass)][0]
    assert props.aspect.customProperties == {}                                   # group-only property omitted


def test_build_mcps_emits_upstream_lineage_from_deps(datahub_emit, monkeypatch):
    from datahub.metadata.schema_classes import UpstreamLineageClass

    up = _Key("music", "fma_raw")
    key = _Key("music", "fma_tracks")
    monkeypatch.setattr(datahub_emit, "_asset_info",
                        lambda: {key: _info(datahub_emit, deps={up}, description="d", group="music")})
    lineage = [m for m in datahub_emit.build_mcps() if isinstance(m.aspect, UpstreamLineageClass)]
    assert len(lineage) == 1
    upstreams = lineage[0].aspect.upstreams
    assert len(upstreams) == 1 and "fma_raw" in upstreams[0].dataset


def test_build_mcps_no_deps_means_no_lineage_aspect(datahub_emit, monkeypatch):
    from datahub.metadata.schema_classes import UpstreamLineageClass

    key = _Key("music", "root")
    monkeypatch.setattr(datahub_emit, "_asset_info",
                        lambda: {key: _info(datahub_emit, deps=frozenset(), description="d", group="music")})
    assert not any(isinstance(m.aspect, UpstreamLineageClass) for m in datahub_emit.build_mcps())


# ── pure type / identifier / URN helpers ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize("type_str,expect", [
    ("int64", "Number"), ("double", "Number"), ("DECIMAL(10,2)", "Number"), ("DataType.INT", "Number"),
    ("boolean", "Boolean"), ("DataType.BOOL", "Boolean"),
    ("varchar", "String"), ("DataType.TEXT", "String"), ("timestamp", "String"),
])
def test_field_type_maps_type_strings(datahub_emit, type_str, expect):
    assert type(datahub_emit._field_type(type_str).type).__name__ == f"{expect}TypeClass"


@pytest.mark.parametrize("value,expect", [(True, "Boolean"), (3, "Number"), (2.5, "Number"), ("x", "String")])
def test_field_type_from_value(datahub_emit, value, expect):
    # bool must be checked before int (bool IS an int in Python) — the ordering is the point
    assert type(datahub_emit._field_type_from_value(value).type).__name__ == f"{expect}TypeClass"


def test_safe_ident_allows_bare_and_rejects_injection(datahub_emit):
    assert datahub_emit._safe_ident("mart_health_2024") == "mart_health_2024"
    for bad in ('a"b', "a;drop", "a b", ""):
        with pytest.raises(ValueError):
            datahub_emit._safe_ident(bad)


def test_soda_dataset_urn_maps_datasource_to_schema(datahub_emit):
    assert "iceberg.datasets_health.brfss" in datahub_emit._soda_dataset_urn("weyland_health", "brfss")
    assert "iceberg.dbt.mart_x" in datahub_emit._soda_dataset_urn("weyland", "mart_x")
    assert "iceberg.dbt.z" in datahub_emit._soda_dataset_urn("unknown_ds", "z")   # falls back to dbt
    assert datahub_emit._soda_dataset_urn("weyland", "t").startswith("urn:li:dataset:")


def test_iceberg_name_precedence_and_defaults(datahub_emit):
    assert datahub_emit._iceberg_name({"identifier": "mart_x"}) == "iceberg.dbt.mart_x"
    assert datahub_emit._iceberg_name({"database": "d", "schema": "s", "alias": "a"}) == "d.s.a"
    assert datahub_emit._iceberg_name({"name": "n"}) == "iceberg.dbt.n"   # identifier/alias absent → name


def test_schema_field_urn_shape(datahub_emit):
    assert datahub_emit._schema_field_urn("urn:li:dataset:x", "col") == "urn:li:schemaField:(urn:li:dataset:x,col)"


def test_sqlglot_schema_from_catalog_builds_nested_dict(datahub_emit):
    catalog = {"sources": {"s1": {"metadata": {"database": "ICEBERG", "schema": "DatasetsMusic", "name": "Tracks"},
                                  "columns": {"Id": {"type": "BIGINT"}, "Title": {"type": "VARCHAR"}}}}}
    schema = datahub_emit._sqlglot_schema_from_catalog(catalog)
    assert schema == {"iceberg": {"datasetsmusic": {"tracks": {"id": "BIGINT", "title": "VARCHAR"}}}}


def test_sqlglot_schema_skips_entries_with_no_columns(datahub_emit):
    catalog = {"nodes": {"n": {"metadata": {"name": "t"}, "columns": {}}}}
    assert datahub_emit._sqlglot_schema_from_catalog(catalog) == {}


def test_store_aspects_shape_with_and_without_fields(datahub_emit):
    from datahub.metadata.schema_classes import (DatasetPropertiesClass, GlobalTagsClass,
                                                 SchemaMetadataClass, UpstreamLineageClass)
    no_fields = datahub_emit._store_aspects("t", "trino", "desc", None, "producer_asset")
    assert [type(a).__name__ for a in no_fields] == [DatasetPropertiesClass.__name__, GlobalTagsClass.__name__,
                                                     UpstreamLineageClass.__name__]
    assert no_fields[0].description == "desc"
    assert "producer_asset" in no_fields[-1].upstreams[0].dataset
    with_fields = datahub_emit._store_aspects("t", "trino", "desc", [object()], "p")
    assert any(isinstance(a, SchemaMetadataClass) for a in with_fields)   # schema inserted when fields present


def test_type_class_from_schema_type(datahub_emit):
    import types as _t
    from datahub.metadata.schema_classes import (BooleanTypeClass, DateTypeClass, NumberTypeClass, StringTypeClass)

    def fld(inner):
        return _t.SimpleNamespace(type=_t.SimpleNamespace(type=inner))
    assert datahub_emit._type_class(fld(NumberTypeClass())) == "measure"
    assert datahub_emit._type_class(fld(DateTypeClass())) == "temporal"
    assert datahub_emit._type_class(fld(BooleanTypeClass())) == "boolean"
    assert datahub_emit._type_class(fld(StringTypeClass())) == "dimension"
    assert datahub_emit._type_class(_t.SimpleNamespace(type=None)) is None


def test_field_leaf_strips_v2_annotations(datahub_emit):
    assert datahub_emit._field_leaf("[version=2.0].[type=struct].[type=double].Danceability") == "danceability"
    assert datahub_emit._field_leaf("plain_col") == "plain_col"


def test_infer_layer_by_substring(datahub_emit):
    assert datahub_emit._infer_layer("mart_health_x") == "mart"
    assert datahub_emit._infer_layer("stg_silver_thing") == "silver"
    assert datahub_emit._infer_layer("rag_chunks") == "serving"
    assert datahub_emit._infer_layer("nothing") is None


def test_infer_source_uses_source_rules(datahub_emit):
    sub, val = datahub_emit._SOURCE_RULES[0]          # drive off the real rule table, not a guess
    assert datahub_emit._infer_source(f"x{sub}y") == val
    assert datahub_emit._infer_source("zzzz_no_rule_matches_this") is None


def test_vector_dataset_meta_recognizes_dataset_collections(datahub_emit):
    desc, producer = datahub_emit._vector_dataset_meta("datasets_music_fma", "qdrant")
    assert "qdrant" in desc and producer == "datasets_music_qdrant_load"
    desc2, producer2 = datahub_emit._vector_dataset_meta("DatasetsHealthNhanes", "weaviate")
    assert producer2 == "datasets_health_weaviate_load"
    assert datahub_emit._vector_dataset_meta("rag_corpus", "qdrant") is None   # RAG store → defaults


def test_mesh_term_index_maps_patterns_to_term_urns(datahub_emit):
    idx = datahub_emit._mesh_term_index()
    assert isinstance(idx, dict) and idx
    for pat, (urn, defn) in idx.items():
        assert urn.startswith("urn:li:glossaryTerm:") and isinstance(defn, str)


# ── emit_* driven with a capturing emitter (assert the real MCP aspects built) ─────────────────────────
class _CapturingEmitter:
    """Records every MCP instead of POSTing to GMS, so we assert what the code BUILT, not that a mock ran."""
    def __init__(self):
        self.mcps = []

    def emit(self, mcp):
        self.mcps.append(mcp)

    def emit_mcp(self, mcp):
        self.mcps.append(mcp)

    def flush(self):
        pass


@pytest.fixture
def captured(datahub_emit, monkeypatch):
    cap = _CapturingEmitter()
    monkeypatch.setattr(datahub_emit, "_gms_emitter", lambda: cap)
    return cap


def test_emit_soda_assertions_builds_info_and_run_per_check(datahub_emit, captured):
    from datahub.metadata.schema_classes import (AssertionInfoClass, AssertionResultTypeClass,
                                                 AssertionRunEventClass, DatasetAssertionScopeClass)
    results = {"checks": [
        {"table": "mart_a", "name": "row_count > 0", "outcome": "pass", "dataSource": "weyland"},
        {"table": "mart_b", "name": "no nulls", "column": "c", "outcome": "fail", "dataSource": "weyland_health"},
        {"name": "orphan check with no table"},   # skipped — no table
    ]}
    n = datahub_emit.emit_soda_assertions(results)
    assert n == 2
    infos = [m.aspect for m in captured.mcps if isinstance(m.aspect, AssertionInfoClass)]
    runs = [m.aspect for m in captured.mcps if isinstance(m.aspect, AssertionRunEventClass)]
    assert len(infos) == 2 and len(runs) == 2
    scopes = {i.datasetAssertion.nativeType: i.datasetAssertion.scope for i in infos}
    assert scopes["no nulls"] == DatasetAssertionScopeClass.DATASET_COLUMN     # column-scoped
    assert scopes["row_count > 0"] == DatasetAssertionScopeClass.DATASET_ROWS  # row-scoped
    outcomes = {r.result.type for r in runs}
    assert outcomes == {AssertionResultTypeClass.SUCCESS, AssertionResultTypeClass.FAILURE}


def test_emit_soda_assertions_urn_is_stable_across_runs(datahub_emit, captured):
    from datahub.metadata.schema_classes import AssertionInfoClass
    check = {"checks": [{"table": "mart_a", "name": "chk", "outcome": "pass", "dataSource": "weyland"}]}
    datahub_emit.emit_soda_assertions(check)
    datahub_emit.emit_soda_assertions(check)
    urns = {m.entityUrn for m in captured.mcps if isinstance(m.aspect, AssertionInfoClass)}
    assert len(urns) == 1   # same (table, check) → same assertion URN → idempotent update


def test_emit_soda_profiles_parses_metric_identities(datahub_emit, captured):
    from datahub.metadata.schema_classes import DatasetProfileClass
    results = {"metrics": [
        {"identity": "metric-Soda Core CLI-weyland-mart_a-row_count", "metricName": "row_count", "value": 200},
        {"identity": "metric-Soda Core CLI-weyland-mart_a-colx-missing_count", "metricName": "missing_count", "value": 20},
        {"identity": "metric-Soda Core CLI-weyland-mart_a-colx-min", "metricName": "min", "value": 1},
        {"identity": "not-a-soda-metric", "metricName": "x", "value": 1},   # ignored
    ]}
    n = datahub_emit.emit_soda_profiles(results)
    assert n == 1
    prof = [m.aspect for m in captured.mcps if isinstance(m.aspect, DatasetProfileClass)][0]
    assert prof.rowCount == 200 and prof.columnCount == 1
    fp = prof.fieldProfiles[0]
    assert fp.fieldPath == "colx" and fp.nullCount == 20 and fp.nullProportion == 0.1 and fp.min == "1"


def test_emit_ge_assertions_reads_results_file(datahub_emit, captured, tmp_path):
    import json
    from datahub.metadata.schema_classes import (AssertionInfoClass, AssertionResultTypeClass,
                                                 AssertionRunEventClass)
    p = tmp_path / "ge.json"
    p.write_text(json.dumps([{"dataset": "iceberg.dbt.mart_a", "results": [
        {"expectation_config": {"expectation_type": "expect_column_values_to_not_be_null",
                                "kwargs": {"column": "c"}}, "success": True, "result": {"observed_value": 5}},
        {"expectation_config": {"expectation_type": "expect_table_row_count_to_be_between", "kwargs": {}},
         "success": False, "result": {}},
    ]}]))
    n = datahub_emit.emit_ge_assertions(str(p))
    assert n == 2
    assert len([m for m in captured.mcps if isinstance(m.aspect, AssertionInfoClass)]) == 2
    runs = [m.aspect for m in captured.mcps if isinstance(m.aspect, AssertionRunEventClass)]
    assert {r.result.type for r in runs} == {AssertionResultTypeClass.SUCCESS, AssertionResultTypeClass.FAILURE}


def test_emit_ge_assertions_missing_file_is_zero(datahub_emit, captured, tmp_path):
    assert datahub_emit.emit_ge_assertions(str(tmp_path / "does_not_exist.json")) == 0
    assert captured.mcps == []


def test_emit_profile_helper(datahub_emit):
    from datahub.metadata.schema_classes import DatasetProfileClass
    cap = _CapturingEmitter()
    assert datahub_emit._emit_profile(cap, "urn:li:dataset:x", None) == 0    # None row_count → no-op
    assert cap.mcps == []
    assert datahub_emit._emit_profile(cap, "urn:li:dataset:x", 42, column_count=3) == 1
    prof = cap.mcps[0].aspect
    assert isinstance(prof, DatasetProfileClass) and prof.rowCount == 42 and prof.columnCount == 3


# ── column-lineage tracer (needs sqlglot; skipped where absent, e.g. the slim scan lane) ───────────────
def test_trace_dbt_columns_no_compiled_sql_returns_empty(datahub_emit):
    assert datahub_emit._trace_dbt_columns({"columns": {"a": {}}}, set()) == {}


def test_trace_dbt_columns_traces_to_catalogued_source(datahub_emit):
    pytest.importorskip("sqlglot")
    node = {"compiled_code": "SELECT t.title AS out_title FROM iceberg.datasets_music.tracks t",
            "columns": {"out_title": {}}}
    out = datahub_emit._trace_dbt_columns(node, {"iceberg.datasets_music.tracks"})
    assert "out_title" in out
    assert ("iceberg.datasets_music.tracks", "title") in out["out_title"]


# ── emit_* that enumerate URNs via a live DataHubGraph (inject a fake graph, assert the built aspects) ──
class _FakeGraph:
    """Stands in for DataHubGraph — a fixed URN set + an optional {aspect_type: value} map for get_aspect, so the
    emitters' enumerate-and-decorate loops run offline against known inputs."""
    def __init__(self, urns=(), aspects=None):
        self._urns = list(urns)
        self._aspects = aspects or {}

    def get_urns_by_filter(self, entity_types=None, **kw):
        return list(self._urns)

    def execute_graphql(self, *a, **k):
        return {}

    def exists(self, urn):
        return False

    def get_aspect(self, urn, aspect_type, *a, **k):
        return self._aspects.get(aspect_type)


@pytest.fixture
def fake_graph(monkeypatch):
    import datahub.ingestion.graph.client as gc

    def _install(urns=(), aspects=None):
        graph = _FakeGraph(urns, aspects)
        monkeypatch.setattr(gc, "DataHubGraph", lambda *a, **k: graph)
        return graph
    return _install


def test_emit_domains_defines_every_domain_and_assigns(datahub_emit, captured, fake_graph):
    from datahub.metadata.schema_classes import DomainPropertiesClass, DomainsClass
    fake_graph(urns=["urn:li:dataset:(urn:li:dataPlatform:trino,iceberg.dbt.mart_spotify_audio,PROD)"])
    n_dom, n_assigned = datahub_emit.emit_domains()
    props = [m.aspect for m in captured.mcps if isinstance(m.aspect, DomainPropertiesClass)]
    assert n_dom == len(datahub_emit._DOMAINS) == len(props)
    assert n_assigned == 3                       # 1 urn enumerated across dataset/chart/dashboard
    assert any(isinstance(m.aspect, DomainsClass) for m in captured.mcps)


def test_emit_data_products_builds_products_and_links_matching_assets(datahub_emit, captured, fake_graph):
    from datahub.metadata.schema_classes import DataProductPropertiesClass, OwnershipClass
    # a URN matching the "Spotify Audio" product pattern
    fake_graph(urns=["urn:li:dataset:(urn:li:dataPlatform:trino,iceberg.dbt.mart_spotify_audio,PROD)"])
    n_p, n_a = datahub_emit.emit_data_products()
    prods = [m.aspect for m in captured.mcps if isinstance(m.aspect, DataProductPropertiesClass)]
    assert n_p == len(datahub_emit._PRODUCTS) == len(prods)
    spotify = next(p for p in prods if p.name == "Spotify Audio")
    assert any("mart_spotify_audio" in a.destinationUrn for a in spotify.assets)   # matched asset linked
    assert n_a >= 3                              # matched across the 3 entity types
    assert any(isinstance(m.aspect, OwnershipClass) for m in captured.mcps)


def test_emit_tags_materializes_the_full_vocabulary(datahub_emit, captured):
    from datahub.metadata.schema_classes import TagPropertiesClass
    n = datahub_emit.emit_tags()
    props = [m.aspect for m in captured.mcps if isinstance(m.aspect, TagPropertiesClass)]
    assert n == len(props) > 0
    names = {p.name for p in props}
    # vocabulary spans medallion tags + structured-property values + field-class tags
    assert names >= set(datahub_emit._TAGS) and names >= set(datahub_emit._FIELD_CLASS_TAGS)


def test_emit_tag_assignments_tags_datasets_by_pattern(datahub_emit, captured, fake_graph):
    from datahub.metadata.schema_classes import GlobalTagsClass
    # a silver-layer iceberg dataset URN → _infer_layer picks it up; get_aspect→None so nothing pre-exists.
    # (name has "silver" but NOT "mart_", since _infer_layer checks mart_ before silver.)
    fake_graph(urns=["urn:li:dataset:(urn:li:dataPlatform:trino,iceberg.datasets_music.silver_tracks,PROD)"])
    n = datahub_emit.emit_tag_assignments()
    tagsets = [m.aspect for m in captured.mcps if isinstance(m.aspect, GlobalTagsClass)]
    assert n == 1 and tagsets
    applied = {a.tag for a in tagsets[0].tags}
    assert any("silver" in t for t in applied)   # medallion layer inferred + applied


def test_emit_structured_properties_defines_facets_and_assigns(datahub_emit, captured, fake_graph):
    from datahub.metadata.schema_classes import (StructuredPropertiesClass, StructuredPropertyDefinitionClass)
    fake_graph(urns=["urn:li:dataset:(urn:li:dataPlatform:trino,iceberg.datasets_music.mart_silver_tracks,PROD)"])
    n_props, n_ds = datahub_emit.emit_structured_properties()
    defs = [m.aspect for m in captured.mcps if isinstance(m.aspect, StructuredPropertyDefinitionClass)]
    assert n_props == len(datahub_emit._STRUCT_PROPS) == len(defs)
    assert n_ds == 1
    assigns = [m.aspect for m in captured.mcps if isinstance(m.aspect, StructuredPropertiesClass)]
    assert assigns and assigns[0].properties


def test_emit_docs_links_attaches_runbooks_by_platform(datahub_emit, captured, fake_graph):
    from datahub.metadata.schema_classes import InstitutionalMemoryClass
    fake_graph(urns=["urn:li:dataset:(urn:li:dataPlatform:trino,iceberg.dbt.mart_x,PROD)"])
    n_ds, n_links = datahub_emit.emit_docs_links()
    assert n_ds == 1 and n_links >= 1
    mem = [m.aspect for m in captured.mcps if isinstance(m.aspect, InstitutionalMemoryClass)][0]
    urls = [e.url for e in mem.elements]
    assert any("runbooks/trino" in u for u in urls)      # platform runbook picked
    assert any("data-mesh-guide" in u for u in urls)     # common docs appended


def test_emit_glossary_publishes_all_nodes_and_terms(datahub_emit, captured):
    from datahub.metadata.schema_classes import GlossaryNodeInfoClass, GlossaryTermInfoClass
    from weyland_pipeline.aidlc_glossary import GLOSSARY
    n_nodes, n_terms = datahub_emit.emit_glossary()
    nodes = [m.aspect for m in captured.mcps if isinstance(m.aspect, GlossaryNodeInfoClass)]
    terms = [m.aspect for m in captured.mcps if isinstance(m.aspect, GlossaryTermInfoClass)]
    assert n_nodes == len(GLOSSARY["nodes"]) == len(nodes) > 0
    assert n_terms == len(GLOSSARY["terms"]) == len(terms) > 0
    assert all(t.termSource == "INTERNAL" and t.parentNode.startswith("urn:li:glossaryNode:") for t in terms)


def test_emit_queries_emits_one_starter_query_per_mart(datahub_emit, captured):
    from datahub.metadata.schema_classes import QueryPropertiesClass, QuerySubjectsClass
    n = datahub_emit.emit_queries()
    props = [m.aspect for m in captured.mcps if isinstance(m.aspect, QueryPropertiesClass)]
    subjects = [m.aspect for m in captured.mcps if isinstance(m.aspect, QuerySubjectsClass)]
    assert n == len(datahub_emit._MART_QUERIES) == len(props) == len(subjects)
    assert all(p.statement.value.strip().startswith("--") for p in props)   # each carries real SQL


def test_emit_ownership_creates_group_and_stamps_datasets(datahub_emit, captured, fake_graph):
    from datahub.metadata.schema_classes import CorpGroupInfoClass, OwnershipClass, OwnershipTypeClass
    fake_graph(urns=["urn:li:dataset:(urn:li:dataPlatform:trino,iceberg.dbt.mart_x,PROD)",
                     "urn:li:dataset:(urn:li:dataPlatform:trino,iceberg.dbt.mart_y,PROD)"])
    n = datahub_emit.emit_ownership()
    assert n == 2
    assert any(isinstance(m.aspect, CorpGroupInfoClass) for m in captured.mcps)
    owns = [m.aspect for m in captured.mcps if isinstance(m.aspect, OwnershipClass)]
    assert len(owns) == 2
    assert owns[0].owners[0].type == OwnershipTypeClass.TECHNICAL_OWNER
    assert owns[0].owners[0].owner == "urn:li:corpGroup:weyland"


def test_emit_dataset_queries_builds_preview_and_aggregate(datahub_emit, captured, fake_graph):
    from datahub.metadata.schema_classes import (NumberTypeClass, OtherSchemaClass, QueryPropertiesClass,
                                                 SchemaFieldClass, SchemaFieldDataTypeClass, SchemaMetadataClass,
                                                 StringTypeClass)
    fields = [
        SchemaFieldClass(fieldPath="genre", type=SchemaFieldDataTypeClass(type=StringTypeClass()),
                         nativeDataType="varchar"),
        SchemaFieldClass(fieldPath="play_count", type=SchemaFieldDataTypeClass(type=NumberTypeClass()),
                         nativeDataType="bigint"),
    ]
    sm = SchemaMetadataClass(schemaName="t", platform="urn:li:dataPlatform:iceberg", version=0, hash="",
                             platformSchema=OtherSchemaClass(rawSchema=""), fields=fields)
    fake_graph(urns=["urn:li:dataset:(urn:li:dataPlatform:iceberg,datasets_music.silver_tracks,PROD)"],
               aspects={SchemaMetadataClass: sm})
    nq, nds = datahub_emit.emit_dataset_queries()
    assert nds == 1 and nq == 2   # a dimension (genre) + a measure (play_count) → preview AND aggregate
    stmts = [m.aspect.statement.value for m in captured.mcps if isinstance(m.aspect, QueryPropertiesClass)]
    assert any("LIMIT 100" in s for s in stmts)          # preview
    assert any("GROUP BY genre" in s for s in stmts)     # aggregate keyed on the dimension


def test_emit_mesh_glossary_no_attach_publishes_vocabulary(datahub_emit, captured):
    from datahub.metadata.schema_classes import GlossaryNodeInfoClass, GlossaryTermInfoClass
    from weyland_pipeline.mesh_vocabulary import NODES, TERMS
    n_nodes, n_terms, n_fields, n_ds = datahub_emit.emit_mesh_glossary(attach=False)
    assert (n_nodes, n_terms, n_fields, n_ds) == (len(NODES), len(TERMS), 0, 0)
    assert len([m for m in captured.mcps if isinstance(m.aspect, GlossaryNodeInfoClass)]) == len(NODES)
    assert len([m for m in captured.mcps if isinstance(m.aspect, GlossaryTermInfoClass)]) == len(TERMS)


def test_emit_mesh_glossary_attach_tags_matching_fields(datahub_emit, captured, fake_graph):
    from datahub.metadata.schema_classes import (EditableSchemaMetadataClass, OtherSchemaClass, SchemaFieldClass,
                                                 SchemaFieldDataTypeClass, SchemaMetadataClass, StringTypeClass)
    idx = datahub_emit._mesh_term_index()
    pat = next(iter(idx))                       # a real mesh-vocabulary field pattern → guaranteed term match
    fields = [SchemaFieldClass(fieldPath=pat, type=SchemaFieldDataTypeClass(type=StringTypeClass()),
                               nativeDataType="varchar")]
    sm = SchemaMetadataClass(schemaName="t", platform="urn:li:dataPlatform:trino", version=0, hash="",
                             platformSchema=OtherSchemaClass(rawSchema=""), fields=fields)
    fake_graph(urns=["urn:li:dataset:(urn:li:dataPlatform:trino,iceberg.dbt.mart_x,PROD)"],
               aspects={SchemaMetadataClass: sm})
    n_nodes, n_terms, n_fields, n_ds = datahub_emit.emit_mesh_glossary(attach=True)
    assert n_ds == 1 and n_fields >= 1
    esm = [m.aspect for m in captured.mcps if isinstance(m.aspect, EditableSchemaMetadataClass)][0]
    info = esm.editableSchemaFieldInfo[0]
    assert info.glossaryTerms and info.glossaryTerms.terms[0].urn == idx[pat][0]   # the exact term attached


def test_emit_field_docs_describes_documented_columns(datahub_emit, captured, fake_graph):
    from datahub.metadata.schema_classes import (EditableSchemaMetadataClass, OtherSchemaClass, SchemaFieldClass,
                                                 SchemaFieldDataTypeClass, SchemaMetadataClass, StringTypeClass)
    from weyland_pipeline.datasets_field_docs import FIELD_DOCS
    # a dataset key with a plain lowercase documented column (matched by exact-column lookup)
    key, col = next((k, c) for k, cols in FIELD_DOCS.items() if cols
                    for c in cols if c == c.lower() and " " not in c)
    fields = [SchemaFieldClass(fieldPath=col, type=SchemaFieldDataTypeClass(type=StringTypeClass()),
                               nativeDataType="varchar")]
    sm = SchemaMetadataClass(schemaName="t", platform="urn:li:dataPlatform:trino", version=0, hash="",
                             platformSchema=OtherSchemaClass(rawSchema=""), fields=fields)
    fake_graph(urns=[f"urn:li:dataset:(urn:li:dataPlatform:trino,iceberg.dbt.{key},PROD)"],
               aspects={SchemaMetadataClass: sm})
    n_ds, n_f = datahub_emit.emit_field_docs()
    assert n_ds == 1 and n_f >= 1
    esm = [m.aspect for m in captured.mcps if isinstance(m.aspect, EditableSchemaMetadataClass)][0]
    assert esm.editableSchemaFieldInfo[0].description == FIELD_DOCS[key][col]   # exact source-doc description


# ── wave 2: feast lineage / external-source terms / lightdash no-op ───────────────────────────────────
def test_emit_feast_links_each_source_to_its_mart(datahub_emit, captured):
    from datahub.metadata.schema_classes import (DatasetPropertiesClass, GlobalTagsClass,
                                                  UpstreamLineageClass)
    n, names = datahub_emit.emit_feast()
    assert n == len(datahub_emit._FEAST_SOURCES) and names == list(datahub_emit._FEAST_SOURCES)
    # every feast source gets props + a `feast` tag + an upstream edge to its dbt mart
    props = [m for m in captured.mcps if isinstance(m.aspect, DatasetPropertiesClass)]
    tags = [m for m in captured.mcps if isinstance(m.aspect, GlobalTagsClass)]
    lineage = [m for m in captured.mcps if isinstance(m.aspect, UpstreamLineageClass)]
    assert len(props) == len(tags) == len(lineage) == n
    assert all(any("feast" in t.tag for t in m.aspect.tags) for m in tags)
    # the track_audio_features source must point at the mart_spotify_audio mart
    taf = next(m for m in lineage if "track_audio_features" in m.entityUrn)
    assert "mart_spotify_audio" in taf.aspect.upstreams[0].dataset


def test_emit_source_terms_cites_external_sources_and_defines_new_terms(datahub_emit, captured, fake_graph):
    from datahub.metadata.schema_classes import GlossaryTermInfoClass
    fake_graph(urns=[])   # no datasets → the description-attach pass (part c) is a clean no-op
    n_cited, n_new, n_fields, n_ds = datahub_emit.emit_source_terms()
    assert n_new == len(datahub_emit._NEW_TERMS)
    assert n_fields == 0 and n_ds == 0                       # empty graph → nothing attached
    terms = [m.aspect for m in captured.mcps if isinstance(m.aspect, GlossaryTermInfoClass)]
    assert len(terms) == n_cited + n_new
    assert terms and all(t.termSource == "EXTERNAL" and t.sourceRef for t in terms)   # every emitted term is cited


def test_emit_lightdash_is_noop_without_api_key(datahub_emit, captured, monkeypatch):
    monkeypatch.delenv("LIGHTDASH_API_KEY", raising=False)
    assert datahub_emit.emit_lightdash() == (0, 0)          # fail-safe: no key → nothing emitted
    assert captured.mcps == []
