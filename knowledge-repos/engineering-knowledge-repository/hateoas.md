---
id: hateoas
tags: [principle, api-design, backend, network, protocol]
surfaces-at: [application-design, functional-design]
related: [rest-constraints, api-versioning, openapi-specification, api-first-design]
complexity: advanced
---

# HATEOAS

## What It Is
Hypermedia As The Engine Of Application State — the final and most misunderstood REST constraint. In a HATEOAS API, responses include hyperlinks to all available next actions. The client starts at a known entry point and discovers everything else by following links — it never constructs URLs itself. This makes the API self-describing and allows the server to evolve URLs without breaking clients. Roy Fielding has stated that APIs without HATEOAS are not truly RESTful — a position most practitioners acknowledge and then consciously ignore.

## When to Apply
- Public APIs with long-lived clients that you cannot redeploy when URLs change (mobile apps, third-party integrations)
- APIs where discoverability is a first-class requirement (developer portals, platform APIs)
- When you want clients to be decoupled from URL structure entirely

## When Not to Apply
- Most internal and partner APIs — the coordination cost of implementing HATEOAS exceeds the benefit when you control both client and server
- Teams without strong API design discipline — inconsistent HATEOAS is worse than none
- When clients are built by the same team and can be updated alongside the server

## Key Concepts
- **Hypermedia Controls**: Links embedded in responses that describe available actions — `rel` (relationship type) and `href` (URL):
  ```json
  {
    "id": "order-123",
    "status": "pending",
    "_links": {
      "self": { "href": "/orders/123" },
      "cancel": { "href": "/orders/123/cancel", "method": "POST" },
      "payment": { "href": "/orders/123/payment" }
    }
  }
  ```
- **`rel` (Link Relation)**: Describes what the link does — `self`, `next`, `prev`, `cancel`, `payment`. IANA maintains a registry of standard relation types
- **HAL (Hypertext Application Language)**: The most widely adopted HATEOAS format — `_links` for links, `_embedded` for nested resources. Simple and tooling-supported
- **JSON:API**: A more comprehensive specification covering HATEOAS, pagination, sparse fieldsets, and relationships. More opinionated than HAL
- **Siren**: Another HATEOAS format that includes actions (with HTTP methods and fields) not just links. More expressive, less adopted
- **The Practical Reality**: Most "REST" APIs skip HATEOAS entirely. Clients hardcode URLs. This works fine when client and server are co-deployed. The tradeoff is real: HATEOAS adds complexity; most teams consciously choose pragmatism over purity
- **Richardson Maturity Model**: A model of REST maturity — Level 0 (HTTP tunnel), Level 1 (resources), Level 2 (HTTP verbs), Level 3 (HATEOAS). Most production APIs are Level 2

## In Practice
Method does not require HATEOAS for internal APIs. For public platform APIs with long-lived third-party clients, HAL-format links are recommended for navigation and pagination (`next`, `prev`, `first`, `last`) — a pragmatic subset of HATEOAS that delivers the highest value at lowest cost. Full HATEOAS is adopted only when client decoupling from URL structure is a hard requirement.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — HATEOAS**: The REST constraint almost no one fully implements — and that's often a conscious, reasonable choice. HATEOAS embeds links to next actions in every response so clients never construct URLs. Maximum benefit: clients decouple from URL structure and discover actions dynamically. Maximum cost: implementation complexity, client sophistication required. Pragmatic middle ground: include `_links` for pagination (`next`/`prev`) and key related resources using HAL format. Know what you're trading away when you skip it. → `engineering-knowledge-repository/hateoas.md`

## Related Entries
- [REST Constraints](rest-constraints.md) — HATEOAS is the sixth and final REST constraint
- [API Versioning](api-versioning.md) — HATEOAS reduces the need for versioning by decoupling clients from URL structure
- [OpenAPI Specification](openapi-specification.md) — OpenAPI documents the links a HATEOAS API exposes
- [API First Design](api-first-design.md) — HATEOAS link design belongs in the API design phase
