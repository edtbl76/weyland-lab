# Jam — capture a UI bug so an agent can read it (B192)

[Jam](https://jam.dev) is a Chrome extension. One capture records the screen, the page's console, its network
requests, the clicks and keystrokes, and browser details, and stores them as a link. Coding agents read a capture through
Bifrost (read-only), so a bug in a lab web UI reaches the agent as evidence instead of a description.

Adopted 2026-11-11 (verdict: [concepts/linear-evaluation.md](../concepts/linear-evaluation.md), row "Integrations → Jam").

## When to use it

- **Use Jam for a bug in a signed-in lab web UI** (Grafana, DataHub, Dagster, Argo CD, Open WebUI, stud.io, …) that an
  agent cannot reproduce itself. The agent's headless browsers stop at Keycloak, so these are the bugs it cannot see.
- **Do not use Jam** for a bug on a public or pre-login page (an agent finds those itself: headless browser, `curl`), for
  backend or CI failures, or for every issue. The free plan allows **30 Jams and 5 recording links a month**, 5-minute
  recordings.

## Capture

1. **Start the recording before the bug happens:** Jam icon → **Record tab**, then reload the page (Ctrl+R) or repeat
   the action that fails. Jam records network and console only while it is recording: a capture started after the page
   loaded holds zero requests (the first B192 capture did).
2. Stop, then **Create**. Give it a plain title of where it happened ("Superset login page"); the evidence speaks for
   itself.
3. For a bug that already happened and will not repeat on demand, Jam's **Instant Replay** keeps a rolling buffer of
   the last moments (enable it in the extension settings first).
4. Paste the link to the agent: "read this Jam and find the cause".

## How agents read it

Through **Bifrost** (`https://bifrost.weyland.lab/mcp`), the same `coding-agents` key every interactive harness already
uses, so nothing per harness. The `Jam` MCP client is registered by `scripts/register_bifrost_mcp_clients.py` (OAuth with
dynamic client registration, scope **`mcp:read`**) and `coding-agents` gets 15 read tools (`JAM_READ` in
`scripts/register_bifrost_vk_mcp.py`): `getDetails`, `getConsoleLogs`, `getNetworkRequests`, `getUserEvents`,
`getEvents`, `getMetadata`, `getScreenshots`, `getFrames`, `analyzeVideo`, `getVideoTranscript`, `getVideoChapters`,
`searchJams`, `listJams`, `listFolders`, `listMembers`. Tools appear as `Jam-<tool>`; a harness started before a change
sees the new tools on its next start.

**Writes are blocked twice:** the key's tool list holds none (`Jam-createComment` → "not allowed for virtual key
'coding-agents'", tested 2026-11-11), and the OAuth token is `mcp:read`. The Jam server's own instructions ask agents to
"post one short comment on the Jam" when they find the cause; they cannot, on purpose. The unattended `agents-read` key
has no Jam access.

Proven 2026-11-11: given only a Jam link, a headless Claude Code on Bifrost named the failing request
(`GET https://superset.weyland.lab/static/service-worker.js` → 404) and the console error in 5 turns (~$0.27).

**Limit seen:** Chrome fetches a service-worker script outside the page's network log, so that 404 was in the console
only. An agent must read both console and network (they do: `getEvents` interleaves them).

## Filing to Linear

Jam's Linear integration (Jam **Settings → Integrations → Linear**) files a capture as an issue with the recording,
console and network attached. File into project **Weyland Auto-Filed** with label **`jam`**: a tool-filed issue carries no
B-number, so it never goes into Weyland Lab (AGENTS.md; `check-linear-sync.sh` would flag it).

**What the filed issue holds, against the Bug template** (proven 2026-11-11, EMA-345): it fills **Evidence** (the video,
uploaded into Linear itself, plus the Jam link for console and network) and **Where** (page URL, browser, network,
time). It leaves **Observed, Expected, Repro and Acceptance criteria** empty, and the title is a generic "Bug caught on"
unless the Jam was named. So complete the issue before it is worked: write Observed/Expected in a line each, or ask an
agent to read the Jam and draft them. The video now lives in Linear's uploads too, so deleting the Jam does not remove it
from the issue.

## Privacy

- Jam scans requests **in the browser** and replaces tokens, cookies and personal data in headers and JSON bodies with
  `JAM_DOES_NOT_SAVE_SECRETS` before upload. Its exact patterns are not published.
- **Not redacted:** the video (whatever is on screen) and hostnames. Both go to Jam's cloud. Capture only what the bug
  needs, and **delete a Jam once its bug is fixed** (Jam UI; the agents' token cannot delete).

## Credentials and rebuild

- **Bifrost's grant:** OAuth, stored in Bifrost's `config.db` (backed up nightly, `bifrost-backup`). After a Bifrost
  rebuild, re-run `register_bifrost_mcp_clients.py`: it prints Jam's `authorize:` URL; open it, approve, then POST the
  printed `complete-oauth` path. Bifrost must have `mcp_external_client_url` set first
  (`register_bifrost_client_config.py`), or the callback points at the in-cluster address and the sign-in cannot finish.
  Commands: [mcp-gateway.md](mcp-gateway.md) § Bifrost MCP library.
- **`JAM_MCP_TOKEN`** in `scripts/.env`: the owner's personal read token (`cli:read mcp:read`), for direct checks from
  rogueone outside Bifrost. Optional. Created and revoked at Jam **Settings → MCP**.
- **Account:** the owner's free Jam workspace. The extension must be signed in to the same workspace the Bifrost grant
  was made for, or agents will not find the capture.
