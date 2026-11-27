# Shared source for the Python golden paths (B261)

The framework-neutral code every Python golden path shares (deep contract v2,
[docs/concepts/golden-path-capabilities.md](../../docs/concepts/golden-path-capabilities.md)). **Edit here, never in a
copy.** [ADR-0020](../../docs/adr/0020-golden-path-shared-code-one-source-synced-copies.md) records why it is copied.

| File | What |
|---|---|
| `items_store.py` | the `ItemStore` contract (plain dicts) and the in-memory store every path runs on by default |
| `items_backends.py` | Postgres, Valkey (cache), Redpanda (`item.created`) and MinIO (attachments); `build_store_from_env()` |
| `v2_smoke.py` | the v2 smoke sequence a path's `smoke.py` runs against its own server |
| `requirements-integration.txt` | the integration clients (owner-approved, pinned) |
| `integration/conftest.py` | refuses to run without real backends (never a skip) |
| `integration/test_items_backends.py` | the adapters against real backends |

**Sync:** `bash scripts/sync-golden-shared.sh` copies every file here (not this README) into each
`golden-paths/python/<framework>/` that holds a `.golden-shared` marker, each copy headed as generated.
`bash scripts/sync-golden-shared.sh --check` runs in CI's `repo-guards` step and fails on any drift. A path's own code
is its framework's (`main.py`, `test_main.py`, `smoke.py`, and `integration/test_api_postgres.py`).
