#!/usr/bin/env python3
"""check-shared-memory.py — prove the shared agent-memory store works end to end (B182, 2026-10-03).

The store is Basic Memory serving ONE directory of Markdown notes on rogueone over MCP (streamable HTTP). Claude Code
writes those files natively (its memory dir is a symlink to it); every other agent reaches the same files over MCP.
This check is the B182 acceptance test and the demo:

  1. reachable  — the MCP server answers and lists its tools. Unreachable is exit 2, never "no memory".
  2. indexed    — every note on disk is in the index (index count == file count).
  3. mcp write  — a note written over MCP lands as a file in the directory, then is deleted.
  4. native     — a note written straight to disk (how Claude Code writes) is found by search within 60 s, then removed.

  usage: check-shared-memory.py [--url URL] [--dir DIR] [--timeout SECONDS] [--read-only]
  --read-only runs checks 1-2 only (no probe notes written) — what the 15-min watchdog uses.
  EXIT: 0 all pass · 1 a check failed (named) · 2 cannot reach / cannot read the store.
"""
import argparse
import asyncio
import glob
import os
import re
import sys
import time
import uuid

DEFAULT_URL = os.environ.get("SHARED_MEMORY_URL", "http://127.0.0.1:8765/mcp")
DEFAULT_DIR = os.path.expanduser(os.environ.get("SHARED_MEMORY_DIR", "~/agent-memory/weyland"))


class CannotReach(Exception):
    pass


def note_files(directory: str) -> list:
    """Markdown notes on disk, relative to the store root (the same set Basic Memory indexes)."""
    return sorted(os.path.relpath(p, directory) for p in glob.glob(os.path.join(directory, "**", "*.md"), recursive=True))


def is_error(res) -> bool:
    return bool(getattr(res, "is_error", getattr(res, "isError", False)))


def text(res) -> str:
    return "\n".join(getattr(c, "text", "") for c in res.content)


async def call(url: str, tool: str, args: dict):
    from mcp import ClientSession
    try:
        from mcp.client.streamable_http import streamable_http_client as client
    except ImportError:  # older SDKs
        from mcp.client.streamable_http import streamablehttp_client as client
    try:
        async with client(url) as streams:
            async with ClientSession(streams[0], streams[1]) as s:
                await s.initialize()
                if tool == "__list_tools__":
                    return [t.name for t in (await s.list_tools()).tools]
                return await s.call_tool(tool, args)
    except Exception as exc:  # connection refused, DNS, HTTP 5xx … all mean "cannot reach"
        raise CannotReach(f"{url}: {type(exc).__name__}: {exc}") from exc


NEED_TOOLS = {"search_notes", "write_note", "read_note", "delete_note", "list_directory"}


async def step_indexed(url: str, directory: str) -> bool:
    """2. the index holds every note on disk. list_directory is PAGINATED (page_size 10); its header carries the total:
    "(page size 10, 214 total items)"."""
    files = note_files(directory)
    res = await call(url, "list_directory", {"dir_name": "/", "depth": 10, "file_name_glob": "*.md", "page_size": 1})
    m = re.search(r"(\d+) total items", text(res))
    if is_error(res) or not m:
        print(f"2. indexed FAIL — could not read the index total from list_directory: {text(res)[:200]!r}")
        return False
    if int(m.group(1)) != len(files):
        print(f"2. indexed FAIL — the index holds {m.group(1)} notes, the directory {len(files)}")
        return False
    print(f"2. indexed OK — the index holds all {len(files)} notes on disk")
    return True


async def step_mcp_write(url: str, directory: str, tag: str) -> bool:
    """3. a note written over MCP lands as a file (it lands just after the call returns — "checksum: unknown")."""
    title = f"check-shared-memory {tag}"
    res = await call(url, "write_note", {"title": title, "directory": "_check", "content": f"probe {tag}"})
    landed = []
    for _ in range(10):
        landed = [f for f in note_files(directory) if tag in f]
        if landed:
            break
        await asyncio.sleep(1)
    await call(url, "delete_note", {"identifier": title})
    if is_error(res) or not landed:
        print(f"3. mcp write FAIL — {text(res)[:200]!r}; file on disk: {landed}")
        return False
    print(f"3. mcp write OK — landed as {landed[0]}")
    return True


async def step_native(url: str, directory: str, tag: str, timeout: float) -> bool:
    """4. a note written straight to disk (how Claude Code writes memory) is searchable within `timeout`."""
    marker = f"nativeprobe{tag}"
    path = os.path.join(directory, f"_check-native-{tag}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(f"---\nname: check-native-{tag}\ndescription: written as a plain file by check-shared-memory\n"
                 f"metadata:\n  type: project\n---\n\n{marker}\n")
    t0 = time.monotonic()
    try:
        while time.monotonic() - t0 < timeout:
            if marker in text(await call(url, "search_notes", {"query": marker})):
                print(f"4. native OK — a plain-file note was searchable after {time.monotonic() - t0:.0f}s")
                return True
            await asyncio.sleep(2)
    finally:
        os.remove(path)
    print(f"4. native FAIL — a plain-file note was not searchable within {timeout:.0f}s")
    return False


async def run(url: str, directory: str, timeout: float, read_only: bool = False) -> int:
    if not os.path.isdir(directory):
        print(f"cannot read the store directory {directory}", file=sys.stderr)
        return 2
    try:
        tools = await call(url, "__list_tools__", {})
    except CannotReach as exc:
        print(f"UNREACHABLE — the shared memory store did not answer ({exc}). Memory is NOT empty; it is down.",
              file=sys.stderr)
        return 2
    if not NEED_TOOLS <= set(tools):
        print(f"1. reachable FAIL — missing tools {sorted(NEED_TOOLS - set(tools))}")
        return 1
    print(f"1. reachable OK — {len(tools)} tools at {url}")

    results = {"indexed": await step_indexed(url, directory)}
    if not read_only:
        tag = uuid.uuid4().hex[:10]
        results["mcp write"] = await step_mcp_write(url, directory, tag)
        results["native"] = await step_native(url, directory, tag, timeout)
    failed = [name for name, ok in results.items() if not ok]
    if failed:
        print(f"FAILED: {', '.join(failed)}")
        return 1
    print("OK — read-only: the store is reachable and its index holds every note." if read_only else
          "OK — the shared memory store is reachable, complete, writable over MCP and sees native writes.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--dir", default=DEFAULT_DIR)
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--read-only", action="store_true", help="checks 1-2 only; write no probe notes")
    a = ap.parse_args(argv)
    try:
        return asyncio.run(run(a.url, os.path.expanduser(a.dir), a.timeout, a.read_only))
    except CannotReach as exc:
        print(f"UNREACHABLE mid-check — {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
