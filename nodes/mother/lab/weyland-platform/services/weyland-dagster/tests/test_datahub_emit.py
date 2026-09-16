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
