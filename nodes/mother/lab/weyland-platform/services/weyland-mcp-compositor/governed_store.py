"""B256: the Basic Memory adapter behind governed writes (governed_write.py's store interface).

Calls go straight to the memory upstream (MEMORY_URL), not through the compositor's proxy, whose read-only rule hides
Basic Memory's write tools from every client. Call shapes observed on the live server (2026-11-23): `write_note` takes a
`metadata` dict merged into the frontmatter and fails if the note exists unless `overwrite`; `edit_note` appends by
file path and merges `metadata`; `read_content` returns the raw file as `text`, and a missing note is a tool error
"Resource not found: <path>". Only that error means "no note": any other failure is raised, because an unreachable
store is never "no memory".
"""
import json

try:   # the real exception at runtime; the unit tests run without fastmcp installed
    from fastmcp.exceptions import ToolError
except ImportError:   # pragma: no cover - exercised only without fastmcp
    class ToolError(Exception):
        pass

NOT_FOUND = "Resource not found"


def _payload(result) -> dict:
    data = getattr(result, "structured_content", None)
    if data:
        return data
    content = getattr(result, "content", None) or []
    return json.loads(content[0].text) if content else {}


class BasicMemoryStore:
    """`call(name, args)` is an awaitable that runs one tool on the memory upstream and returns its result."""

    def __init__(self, call):
        self._call = call

    async def read_raw(self, path: str):
        try:
            result = await self._call("read_content", {"path": path})
        except ToolError as exc:
            if str(exc).startswith(NOT_FOUND) or f"{NOT_FOUND}:" in str(exc):
                return None
            raise
        return _payload(result).get("text")

    async def write(self, title: str, directory: str, content: str, metadata: dict, overwrite: bool) -> str:
        await self._call("write_note", {"title": title, "directory": directory or "/", "content": content,
                                        "metadata": metadata, "overwrite": overwrite})
        return f"{directory}/{title}.md" if directory else f"{title}.md"

    async def append(self, path: str, content: str, metadata: dict) -> str:
        await self._call("edit_note", {"identifier": path, "operation": "append", "content": content,
                                       "metadata": metadata})
        return path


def client_call(url: str):
    """A `call` for BasicMemoryStore that opens one MCP session per call to `url` (stateless, like the fleet)."""
    from fastmcp import Client

    async def call(name, args):
        async with Client(url) as client:
            return await client.call_tool(name, args)
    return call
