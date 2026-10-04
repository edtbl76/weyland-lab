"""Tests for the compositor's upstream config + read-only allowlist (B182, 2026-10-03).

The fleet is READ surfaces only (see app.py). Adding the shared agent memory (Basic Memory) as an upstream must not
bring its write/delete tools along. FastMCP 3.4.5's per-server `tools`/`include_tags` config does NOT do this — the tag
transform is not applied, so include_tags filtered out all 21 tools (observed in a real container). The allowlist is
enforced by middleware instead (app.py), driven by `is_blocked()` here: hidden from tools/list AND refused on call.
A tool a future Basic Memory version adds is blocked unless listed in MEMORY_READ_TOOLS.

Tool names: with several upstreams FastMCP prefixes each tool with its upstream name (`memory_search_notes`); with a
single upstream it does not (observed). is_blocked handles both.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config

MEM = {"MEMORY_URL": "http://store:8765/mcp"}
WRITE_TOOLS = ("write_note", "edit_note", "delete_note", "move_note", "create_memory_project", "delete_project")


def test_memory_is_skipped_unless_its_url_is_set():
    assert "memory" not in config.build_servers({})


def test_memory_mounts_plainly_when_its_url_is_set():
    m = config.build_servers(MEM)["memory"]
    assert m == {"url": "http://store:8765/mcp", "transport": "http"}


def test_the_other_upstreams_are_unchanged():
    s = config.build_servers({})
    assert set(s) == {"context", "grafana", "trino", "k8s", "postgres", "neo4j", "datahub"}
    assert s["postgres"]["transport"] == "sse"


def test_an_empty_url_still_skips_an_upstream():
    assert "grafana" not in config.build_servers({"GRAFANA_URL": ""})


def test_in_the_fleet_memory_write_tools_are_blocked_and_read_tools_pass():
    servers = config.build_servers(MEM)          # 8 upstreams -> prefixed names
    for w in WRITE_TOOLS:
        assert config.is_blocked(f"memory_{w}", servers), w
    for r in config.MEMORY_READ_TOOLS:
        assert not config.is_blocked(f"memory_{r}", servers), r


def test_a_tool_a_future_version_adds_is_blocked_by_default():
    assert config.is_blocked("memory_brand_new_tool", config.build_servers(MEM))


def test_other_upstreams_tools_are_never_blocked():
    servers = config.build_servers(MEM)
    assert not config.is_blocked("k8s_pods_list", servers)
    assert not config.is_blocked("grafana_query_prometheus", servers)
    assert not config.is_blocked("context_search", servers)


def test_single_upstream_names_are_unprefixed_and_still_filtered():
    only_memory = {"memory": {"url": "http://store:8765/mcp", "transport": "http"}}
    assert config.is_blocked("delete_note", only_memory)
    assert not config.is_blocked("search_notes", only_memory)


def test_without_the_memory_upstream_nothing_is_blocked():
    assert not config.is_blocked("memory_delete_note", config.build_servers({}))


# --- 2026-10-04: the fleet's memory searches are SEMANTIC ---------------------------------------------------------------
# Measured: for "rogueone GPU freeze" the note that answers it (rogueone-gpu-freeze-vram) is #1 by semantic/vector search
# and ABSENT from the top 10 by text and by the default hybrid (its full-text half dominates short keyword queries — the
# kind a small model writes). The operator's 7B brain also passes search_type="text" on its own. So the fleet rewrites
# default/text/hybrid to semantic; an explicit exact lookup (title, permalink) is left alone.


def test_a_default_text_or_hybrid_memory_search_becomes_semantic():
    servers = config.build_servers(MEM)
    for given in ({"query": "q"}, {"query": "q", "search_type": "text"}, {"query": "q", "search_type": "hybrid"},
                  {"query": "q", "search_type": None}):
        out = config.rewrite_arguments("memory_search_notes", dict(given), servers)
        assert out == {"query": "q", "search_type": "semantic"}, given


def test_an_exact_lookup_or_explicit_vector_search_is_left_alone():
    servers = config.build_servers(MEM)
    for st in ("title", "permalink", "semantic", "vector"):
        assert config.rewrite_arguments("memory_search_notes", {"query": "q", "search_type": st}, servers)["search_type"] == st


def test_other_tools_arguments_are_never_rewritten():
    servers = config.build_servers(MEM)
    args = {"query": "q", "search_type": "text"}
    assert config.rewrite_arguments("memory_read_note", dict(args), servers) == args
    assert config.rewrite_arguments("datahub_search", dict(args), servers) == args


def test_single_upstream_unprefixed_search_is_rewritten_too():
    only_memory = {"memory": {"url": "http://store:8765/mcp", "transport": "http"}}
    assert config.rewrite_arguments("search_notes", {"query": "q"}, only_memory)["search_type"] == "semantic"


def test_without_the_memory_upstream_nothing_is_rewritten():
    assert config.rewrite_arguments("memory_search_notes", {"query": "q"}, config.build_servers({})) == {"query": "q"}
