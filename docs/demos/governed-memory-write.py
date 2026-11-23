"""B256 live proof: governed writes through the REAL gateway with the operator's own Keycloak token (minted inside the
pod by act._token; never printed). Identity comes from the token (azp = weyland-operator), set by the gateway."""
import asyncio
import sys

sys.path.insert(0, "/app")
from act import GATEWAY, _token  # noqa: E402
from mcp import ClientSession  # noqa: E402
from mcp.client.streamable_http import streamablehttp_client  # noqa: E402

URL = GATEWAY.rstrip("/") + "/mcp-memory"
TASK_DIR = "task/b256"   # the demo's own task layer


async def call(name, args):
    headers = {"Authorization": f"Bearer {_token()}"}
    async with streamablehttp_client(URL, headers=headers) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            if name == "list":
                return sorted(t.name for t in (await s.list_tools()).tools)
            res = await s.call_tool(name, args)
            text = " ".join(getattr(c, "text", "") for c in res.content)
            return ("REFUSED " if res.isError else "OK ") + text[:150]


async def main():
    print("tools:", await call("list", None))
    t = {"directory": TASK_DIR, "title": "gateway e2e", "source": "B256"}
    print("1 operator creates a task note:", await call("governed_write_note", {**t, "operation": "create",
          "content": "Written through the real gateway with the operator's own Keycloak token (B256 live proof)."}))
    print("2 operator writes project memory:", await call("governed_write_note", {"directory": "", "title": "b256 gw forbidden",
          "source": "B256", "operation": "create", "content": "x"}))
    print("3 operator writes person/edward:", await call("governed_write_note", {"directory": "person/edward",
          "title": "b256 gw forbidden", "source": "B256", "operation": "create", "content": "x"}))
    print("4 operator reads it back:", await call("governed_read_note", {"directory": TASK_DIR, "title": "gateway e2e"}))
    print("5 Basic Memory's own write_note:", await call("write_note", {"title": "b256 bypass", "directory": TASK_DIR,
          "content": "x"}))

asyncio.run(main())
