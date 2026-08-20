---
id: long-polling-sse-websockets
tags: [pattern, api-design, backend, network]
surfaces-at: [application-design, nfr-requirements]
related: [rest-constraints, grpc, api-gateway-design, polling-consumer]
complexity: intermediate
---

# Long Polling, SSE, and WebSockets

## What It Is
Three patterns for delivering real-time or near-real-time data from server to client, each with different tradeoffs in complexity, HTTP compatibility, directionality, and infrastructure requirements. Choosing the right pattern depends on the update frequency, directionality of communication, and infrastructure constraints.

## When to Apply
- Any feature requiring the client to receive updates without explicit polling: notifications, live feeds, chat, dashboards, collaborative editing
- Choose the pattern based on the communication model required

## Key Concepts

**Long Polling**:
- Client sends a request; server holds it open until data is available or a timeout occurs, then responds. Client immediately sends the next request
- Effectively simulates push over standard HTTP request-response
- Works through all proxies and firewalls — it's just HTTP
- Higher server resource cost than SSE (connection held per client)
- Best for: infrequent updates where strict HTTP compatibility is required

**Server-Sent Events (SSE)**:
- A persistent HTTP connection over which the server pushes a stream of `text/event-stream` events
- Unidirectional: server → client only
- Automatic reconnection built into the browser `EventSource` API
- Works over HTTP/1.1 and HTTP/2 (HTTP/2 multiplexes, avoiding connection limits)
- Simpler than WebSockets for server-push use cases — no protocol upgrade, no framing complexity
- Best for: notifications, live feeds, progress updates, dashboards

**WebSockets**:
- A full-duplex, persistent TCP connection upgraded from HTTP via `Upgrade: websocket` header
- Bidirectional: client and server can send messages at any time
- Lower overhead per message than HTTP once the connection is established
- More complex: requires WebSocket-aware load balancers, connection state management, reconnection logic
- Not natively supported by HTTP/2 (though HTTP/2 has `h2c` WebSocket support)
- Best for: chat, collaborative editing, multiplayer, bidirectional real-time interactions

**Decision Matrix**:
| | Long Polling | SSE | WebSockets |
|---|---|---|---|
| Direction | Server→Client | Server→Client | Bidirectional |
| HTTP compatible | Yes | Yes | Upgrade required |
| Auto-reconnect | Manual | Built-in | Manual |
| Complexity | Low | Low | High |
| Use case | Infrequent updates | Streams, notifications | Chat, collaboration |

## In Practice
Method uses SSE for notification feeds, progress indicators, and live dashboard updates — it's simpler than WebSockets and sufficient for unidirectional push. WebSockets are used for collaborative features and chat. Long polling is a fallback for environments where SSE is problematic (some corporate proxies buffer SSE streams).

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Long Polling, SSE, WebSockets**: Don't default to WebSockets — most real-time use cases are server→client only and SSE is simpler (plain HTTP, auto-reconnect, works through proxies). Use SSE for notifications, live feeds, progress. Use WebSockets only when you need bidirectional communication (chat, collaborative editing). Long polling is the compatibility fallback. Ensure your load balancer and API gateway support persistent connections for SSE and WebSockets. → `engineering-knowledge-repository/api-design/long-polling-sse-websockets.md`

## Related Entries
- [REST Constraints](rest-constraints.md) — SSE and long polling stay within HTTP semantics; WebSockets break out
- [gRPC](grpc.md) — gRPC streaming is an alternative for service-to-service real-time communication
- [API Gateway Design](api-gateway-design.md) — gateways must be configured to support persistent connections
- [Polling Consumer](polling-consumer.md) — the async polling pattern for job status (distinct from long polling)
