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
        # No `project` argument, ever: each server here is constrained to one project and ignores it (2026-11-23).
        await self._call("write_note", {"title": title, "directory": directory or "/", "content": content,
                                        "metadata": metadata, "overwrite": overwrite})
        return f"{directory}/{title}.md" if directory else f"{title}.md"

    async def append(self, path: str, content: str, metadata: dict) -> str:
        await self._call("edit_note", {"identifier": path, "operation": "append", "content": content,
                                       "metadata": metadata})
        return path


class RoutingStore:
    """The store governed_write talks to: the shared server for every shared layer, and each person's OWN Basic Memory
    server (constrained to `person-<name>`) for that person's layer (owner, 2026-11-23: A strict). A person with no
    server is refused: their note is never written to the shared store instead."""

    def __init__(self, shared, persons: dict):
        self._shared, self._persons = shared, dict(persons)

    def _pick(self, project):
        if project is None:
            return self._shared
        name = project.removeprefix("person-")
        if not project.startswith("person-") or name not in self._persons:
            raise ToolError(f"the person layer for {name} is not provisioned (no Basic Memory server for it)")
        return self._persons[name]

    async def read_raw(self, path, project=None):
        return await self._pick(project).read_raw(path)

    async def write(self, title, directory, content, metadata, overwrite, project=None):
        return await self._pick(project).write(title, directory, content, metadata, overwrite)

    async def append(self, path, content, metadata, project=None):
        return await self._pick(project).append(path, content, metadata)


def person_urls(env) -> dict:
    """{person: MCP URL} from PERSON_MEMORY_URLS="name=url,name=url" (each person's own Basic Memory server)."""
    out = {}
    for item in (env.get("PERSON_MEMORY_URLS") or "").split(","):
        name, sep, url = item.strip().partition("=")
        if sep and name and url:
            out[name.strip()] = url.strip()
    return out


def client_call(url: str):
    """A `call` for BasicMemoryStore that opens one MCP session per call to `url` (stateless, like the fleet)."""
    from fastmcp import Client

    async def call(name, args):
        async with Client(url) as client:
            return await client.call_tool(name, args)
    return call
