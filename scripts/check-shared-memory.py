#!/usr/bin/env python3
"""check-shared-memory.py — prove the shared agent-memory store works end to end (B182, 2026-10-03).

The store is Basic Memory serving ONE directory of Markdown notes on rogueone over MCP (streamable HTTP). Claude Code
writes those files natively (its memory dir is a symlink to it); every other agent reaches the same files over MCP.
This check is the B182 acceptance test and the demo:

  1. reachable  — the MCP server answers and lists its tools. Unreachable is exit 2, never "no memory".
  2. indexed    — every note on disk is in the index (index count == file count).
  3. mcp write  — a note written over MCP lands as a file in the directory, then is deleted.
  4. native     — a note written straight to disk (how Claude Code writes) is found by search within 60 s, then removed.
  0. index files — (no server needed; every mode) the two-tier index (B255, 2026-11-20): MEMORY.md, the core every
                  Claude Code session loads (Claude Code loads only its first 25 KB / 200 lines), is within its 12 KB
                  budget; every note is linked from MEMORY.md or MEMORY-catalog.md; no link points at a missing note.

  usage: check-shared-memory.py [--url URL] [--dir DIR] [--timeout SECONDS] [--read-only]
  --read-only runs checks 0-2 only (no probe notes written) — what the 15-min watchdog uses.
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


CORE = "MEMORY.md"
CATALOG = "MEMORY-catalog.md"
CORE_BUDGET_BYTES = 12 * 1024   # half of the 25 KB Claude Code loads from MEMORY.md; the rest is silently dropped
_LINK = re.compile(r"\]\(([^)\s]+)\)")


def _targets(text: str) -> set:
    """Note paths an index file links to, normalised to end in .md (some links omit it)."""
    return {t if t.endswith(".md") else t + ".md" for t in _LINK.findall(text) if "://" not in t}


# B256 (2026-11-23): the task and person layers (task/<item>/, person/<name>/) are scoped context, not project memory:
# the indexes do not list them (docs/design/shared-context-design.md § Context layers).
LAYER_DIRS = ("task/", "person/")


def index_problems(directory: str, budget: int = CORE_BUDGET_BYTES) -> list:
    """Problems with the two-tier index, named; [] when the core is within budget and every project note is linked.
    Notes in the task and person layers need no index entry, but a link to one that does not exist is still a problem."""
    on_disk = set(note_files(directory)) - {CORE, CATALOG}
    notes = {n for n in on_disk if not n.startswith(LAYER_DIRS)}
    if not notes:
        return ["no notes found: the index check would pass vacuously"]
    core_path, cat_path = os.path.join(directory, CORE), os.path.join(directory, CATALOG)
    if not os.path.exists(core_path):
        return [f"{CORE} is missing: Claude Code would load no memory index"]
    problems = []
    core = open(core_path, encoding="utf-8").read()
    size = len(core.encode("utf-8"))
    if size > budget:
        problems.append(f"{CORE} is {size} bytes, over its {budget}-byte budget: move entries to {CATALOG}")
    catalog = open(cat_path, encoding="utf-8").read() if os.path.exists(cat_path) else ""
    for name, text in ((CORE, core), (CATALOG, catalog)):
        for t in sorted(_targets(text) - on_disk - {CORE, CATALOG}):
            problems.append(f"{name} links {t}, which does not exist")
    linked = _targets(core) | _targets(catalog)
    problems += [f"{n} is in neither {CORE} nor {CATALOG}" for n in sorted(notes - linked)]
    return problems


# B256 (2026-11-23): every note written from now on carries provenance: the governed gateway stamps other agents'
# writes, and .claude/hooks/memory-provenance.py stamps Claude Code's native ones. A note changed after this moment with
# no `updated_by` was written around both (a Bash edit, another tool). The notes from before carry none (grandfathered).
PROVENANCE_SINCE = 1795489200   # 2026-11-24T03:00:00Z: the hook went live


def provenance_problems(directory: str, cutoff: int = PROVENANCE_SINCE) -> list:
    out = []
    for rel in note_files(directory):
        if rel in (CORE, CATALOG) or rel.startswith("_check/"):
            continue
        path = os.path.join(directory, rel)
        if os.path.getmtime(path) <= cutoff:
            continue
        head = open(path, encoding="utf-8").read().split("\n---\n", 1)[0]
        if not re.search(r"^updated_by:", head, re.M):
            out.append(f"{rel} changed after provenance began with no updated_by (written around the hook?)")
    return out


def step_provenance(directory: str) -> bool:
    problems = provenance_problems(directory)
    if problems:
        print("0b. provenance FAIL — " + "; ".join(problems[:10]) + (f" (+{len(problems) - 10} more)" if len(problems) > 10 else ""))
        return False
    print("0b. provenance OK — every note changed since provenance began carries updated_by")
    return True


def _front_value(head: str, key: str) -> str | None:
    m = re.search(rf"^{key}:\s*['\"]?([^'\"\n]+)['\"]?\s*$", head, re.M)
    return m.group(1).strip() if m else None


def review_due(directory: str, today: str | None = None) -> list:
    """Notes past their `review_by` date (stamped by governed writes, B256 step 4), for a person to confirm or supersede.
    Superseded notes (`invalid_at`) are skipped. A list to act on, never a failure and never a deletion."""
    today = today or time.strftime("%Y-%m-%d", time.gmtime())
    due = []
    for rel in note_files(directory):
        if rel in (CORE, CATALOG) or rel.startswith("_check/"):
            continue
        head = open(os.path.join(directory, rel), encoding="utf-8").read().split("\n---\n", 1)[0]
        review_by = _front_value(head, "review_by")
        if review_by and review_by[:10] < today and not _front_value(head, "invalid_at"):
            due.append(f"{rel} (review by {review_by[:10]})")
    return due


def step_review_due(directory: str) -> bool:
    due = review_due(directory)
    print(f"0c. review due: {len(due)} note(s)" + (" — " + "; ".join(due[:10]) if due else "") + " (informational)")
    return True


def step_index_files(directory: str) -> bool:
    problems = index_problems(directory)
    if problems:
        print("0. index files FAIL — " + "; ".join(problems[:10]) + (f" (+{len(problems) - 10} more)" if len(problems) > 10 else ""))
        return False
    size = os.path.getsize(os.path.join(directory, CORE))
    print(f"0. index files OK — {CORE} {size} of {CORE_BUDGET_BYTES} bytes; every note linked from {CORE} or {CATALOG}")
    return True


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
NATIVE_WAIT_S = 60.0   # how long step 4 waits for a plain-file note to become searchable (--timeout)


async def step_indexed(url: str, directory: str) -> bool:
    """2. the index holds every note on disk. list_directory is PAGINATED (page_size 10); its header carries the total:
    "(page size 10, 214 total items)"."""
    files = note_files(directory)
    res = await call(url, "list_directory", {"dir_name": "/", "depth": 10, "file_name_glob": "*.md", "page_size": 1})
    m = re.search(r"\b(\d{1,9}) total items", text(res))
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


def _write_probe(path: str, tag: str, marker: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(f"---\nname: check-native-{tag}\ndescription: written as a plain file by check-shared-memory\n"
                 f"metadata:\n  type: project\n---\n\n{marker}\n")


async def step_native(url: str, directory: str, tag: str) -> bool:
    """4. a note written straight to disk (how Claude Code writes memory) is searchable within NATIVE_WAIT_S."""
    marker = f"nativeprobe{tag}"
    path = os.path.join(directory, f"_check-native-{tag}.md")
    await asyncio.to_thread(_write_probe, path, tag, marker)
    t0 = time.monotonic()
    try:
        async with asyncio.timeout(NATIVE_WAIT_S):
            while marker not in text(await call(url, "search_notes", {"query": marker})):
                await asyncio.sleep(2)
        print(f"4. native OK — a plain-file note was searchable after {time.monotonic() - t0:.0f}s")
        return True
    except TimeoutError:
        print(f"4. native FAIL — a plain-file note was not searchable within {NATIVE_WAIT_S:.0f}s")
        return False
    finally:
        await asyncio.to_thread(os.remove, path)


async def run(url: str, directory: str, read_only: bool = False) -> int:
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

    results = {"index files": step_index_files(directory), "provenance": step_provenance(directory),
               "review due": step_review_due(directory),
               "indexed": await step_indexed(url, directory)}
    if not read_only:
        tag = uuid.uuid4().hex[:10]
        results["mcp write"] = await step_mcp_write(url, directory, tag)
        results["native"] = await step_native(url, directory, tag)
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
        global NATIVE_WAIT_S
        NATIVE_WAIT_S = a.timeout
        return asyncio.run(run(a.url, os.path.expanduser(a.dir), a.read_only))
    except CannotReach as exc:
        print(f"UNREACHABLE mid-check — {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
