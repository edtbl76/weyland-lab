# Demo: governed writes to the shared memory (B256)

An agent writes to the shared memory as itself, through the real gateway: allowed in its layer, refused elsewhere, and
stamped with who wrote it. Flow: [flow-governed-memory-write](../diagrams/flow-governed-memory-write.md); runbook:
[shared-agent-memory.md § Governed writes](../runbooks/shared-agent-memory.md). Run live on 2026-11-23 against
`git-a2b44536`; outputs below are from that run. It creates one note in `task/b256/` (teardown at the end).

## CLI walkthrough

The test runs inside the operator's pod, which mints the operator's own Keycloak token (`act._token`; never printed),
and calls `/mcp-memory` on the gateway. The script is the B256 live proof: it lists the tools, creates a task note,
tries project memory and `person/edward`, reads the note back, and tries Basic Memory's own `write_note`.

[rogueone]
```
kubectl -n weyland exec -i deploy/weyland-operator -- python - < /home/edwardmangini/IdeaProjects/weyland/docs/demos/governed-memory-write.py
```

Expected (2026-11-23):

```
tools: ['build_context', 'governed_read_note', 'governed_write_note', 'list_directory', 'read_content', 'read_note', 'recent_activity', 'search_notes', 'view_note']
1 operator creates a task note: OK {"result":"created","path":"task/b256/gateway e2e.md"}
2 operator writes project memory: REFUSED weyland-operator may not write the project layer
3 operator writes person/edward: REFUSED weyland-operator may not write the person layer
4 operator reads it back: OK {"path":"task/b256/gateway e2e.md","sha256":"…","text":"---\ntitle: gateway e2e …
5 Basic Memory's own write_note: REFUSED write_note is not allowed through the read-only fleet
```

A second run prints `REFUSED … exists` on line 1 (create never overwrites); run the teardown first to start clean.

The note on disk carries its author:

[rogueone]
```
head -11 "/home/edwardmangini/agent-memory/weyland/task/b256/gateway e2e.md"
```

Expected: `created_by: agent:weyland-operator`, `author_kind: agent`, `source: B256`, `on_behalf_of: null`, UTC times.
And each attempt left one audit line:

[rogueone]
```
kubectl -n weyland logs deploy/weyland-mcp-compositor-memory --since=1h | grep mcp-memory-write
```

## UI walkthrough (UAT, eyes on)

In Open WebUI, with the memory tool server connected (runbook § Open WebUI), ask: "Use governed_write_note to append
'checked in the UI' to the note 'gateway e2e' in directory task/b256, source B256." Confirm the reply says it was
appended, then open the note on rogueone: `updated_by` is now `user:<your username>`, `author_kind` stays as created,
and `on_behalf_of` is `null`. Ask it to write to `person/someone-else`: the reply is a refusal naming that person.

## Teardown

[rogueone]
```
rm "/home/edwardmangini/agent-memory/weyland/task/b256/gateway e2e.md"
```
