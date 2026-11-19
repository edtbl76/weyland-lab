#!/usr/bin/env python3
"""memory-recall-probe.py — does a natural question find the shared-memory note that answers it? (B250, 2026-11-19)

Lab Recall answered "How does Weyland manage ADRs?" with "Actionable Design Reviews": the memory search returned
hardware-topology, weyland-guard-b70 and prompt-federation-b103, not adr-log-b248. This asks each question in the cases
file the way Open WebUI and the operator do — a SEMANTIC search, which is what the MCP compositor rewrites every memory
search to (weyland-mcp-compositor config.py SEMANTIC_SEARCH) — against the same Basic Memory index, and fails when the
expected note is not in the top 3.

  usage: memory-recall-probe.py [--url URL] [--cases FILE] [--top N]
  EXIT: 0 every question finds its note · 1 a miss (each named, with what came back instead)
        2 the store is unreachable, or a search errored or returned nothing (never a pass)
Runbook: docs/runbooks/shared-agent-memory.md § Recall probe. Run with: uv run -q --with mcp python <this file>
"""
import argparse
import asyncio
import os
import pathlib
import re
import sys

DEFAULT_URL = os.environ.get("SHARED_MEMORY_URL", "http://127.0.0.1:8765/mcp")
DEFAULT_CASES = pathlib.Path(__file__).resolve().parent / "memory-recall-cases.tsv"
TOP = 3
HIT = re.compile(r"^### ([^\n]+)", re.MULTILINE)   # one "### <note>" heading per hit, in rank order (observed)


class CannotReach(Exception):
    pass


def titles(result_text: str) -> list:
    return [t.strip() for t in HIT.findall(result_text)]


def load_cases(path) -> list:
    cases = []
    for n, line in enumerate(pathlib.Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = [p.strip() for p in line.split("\t")]
        if len(parts) != 2 or not all(parts):
            raise ValueError(f"{path} line {n}: want 'question<TAB>expected note', got {line!r}")
        cases.append((parts[0], parts[1]))
    if not cases:
        raise ValueError(f"{path}: no cases")
    return cases


async def run(cases, search, top: int = TOP) -> int:
    """search(query) -> (is_error, result text); it raises CannotReach when the store does not answer."""
    misses, broken = 0, 0
    for query, want in cases:
        try:
            is_error, text = await search(query)
        except CannotReach as exc:
            print(f"UNREACHABLE  {query!r}: {exc}. Memory is not empty; it did not answer.")
            return 2
        got = titles(text)
        if is_error or not got:
            print(f"NO RESULTS   {query!r}: {'error' if is_error else 'empty'} — {text.strip()[:160]!r}")
            broken += 1
        elif want in got[:top]:
            print(f"hit #{got.index(want) + 1}       {query!r} -> {want}")
        else:
            misses += 1
            print(f"MISS         {query!r}: wanted {want} in the top {top}, got {got[:top]}")
    if broken:
        print(f"FAILED: {broken} search(es) returned no results or an error (not a pass)")
        return 2
    if misses:
        print(f"FAILED: {misses} of {len(cases)} question(s) did not find their note")
        return 1
    print(f"OK — all {len(cases)} question(s) found their note in the top {top}")
    return 0


def mcp_search(url: str, top: int):
    async def search(query):
        from mcp import ClientSession
        try:
            from mcp.client.streamable_http import streamable_http_client as client
        except ImportError:  # older SDKs
            from mcp.client.streamable_http import streamablehttp_client as client
        try:
            async with client(url) as streams:
                async with ClientSession(streams[0], streams[1]) as s:
                    await s.initialize()
                    res = await s.call_tool("search_notes",
                                            {"query": query, "search_type": "semantic", "page_size": top})
        except Exception as exc:  # refused, DNS, HTTP 5xx: all mean the store did not answer
            raise CannotReach(f"{url}: {type(exc).__name__}: {exc}") from exc
        is_error = bool(getattr(res, "is_error", getattr(res, "isError", False)))
        return is_error, "\n".join(getattr(c, "text", "") for c in res.content)
    return search


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--cases", default=str(DEFAULT_CASES))
    ap.add_argument("--top", type=int, default=TOP)
    a = ap.parse_args(argv)
    try:
        cases = load_cases(a.cases)
    except (OSError, ValueError) as exc:
        print(f"cannot read the cases: {exc}", file=sys.stderr)
        return 2
    return asyncio.run(run(cases, mcp_search(a.url, a.top), a.top))


if __name__ == "__main__":
    sys.exit(main())
