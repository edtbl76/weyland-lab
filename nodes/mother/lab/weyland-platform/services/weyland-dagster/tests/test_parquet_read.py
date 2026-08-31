"""First tests for weyland-dagster (B78 step 2, EMA-69).

Targets the dagster-free ``parquet_read`` leaf module via the ``parquet_read`` fixture, which loads it
in isolation — proving both the harness and that the fast lane never imports the dagster runtime.
``needed_columns`` is the projection the step-3 read will pull; getting it wrong is what would make the
read either materialise columns it does not need (the OOM this whole thread is about) or drop one the
spec relies on.
"""


def test_needed_columns_unions_every_referenced_field(parquet_read):
    # The OFF spec confirmed in step 1: text = product_name+brands+categories_en, filter product_name,
    # id code, payload product_name+brands+url.
    spec = {
        "text": ["product_name", "brands", "categories_en"],
        "filter": "product_name",
        "id": "code",
        "payload": ["product_name", "brands", "url"],
    }
    cols = parquet_read.needed_columns(spec)
    for referenced in ("product_name", "brands", "categories_en", "code", "url"):
        assert referenced in cols, f"{referenced} must be projected"
    # product_name appears in text, filter AND payload — it must be projected exactly once.
    assert cols.count("product_name") == 1
    assert len(cols) == len(set(cols)), "projection must be de-duplicated"


def test_needed_columns_preserves_first_seen_order(parquet_read):
    spec = {"text": ["b", "a"], "id": "c", "payload": ["a", "d"]}
    # b, a (text) → c (id) → d (payload; a already seen)
    assert parquet_read.needed_columns(spec) == ["b", "a", "c", "d"]


def test_needed_columns_empty_spec_projects_nothing(parquet_read):
    assert parquet_read.needed_columns({}) == []


def test_needed_columns_ignores_absent_and_empty_keys(parquet_read):
    assert parquet_read.needed_columns({"text": [], "payload": None, "id": ""}) == []
