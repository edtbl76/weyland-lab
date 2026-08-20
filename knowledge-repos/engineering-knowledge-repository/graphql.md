---
id: graphql
tags: [protocol, api-design, backend, network]
surfaces-at: [application-design, functional-design]
related: [rest-constraints, grpc, api-first-design, openapi-specification]
complexity: intermediate
---

# GraphQL

## What It Is
A query language and runtime for APIs, developed at Facebook and open-sourced in 2015. Clients specify exactly the data they need in a query — no over-fetching of unused fields, no under-fetching requiring multiple requests. The schema defines all available types and relationships; resolvers provide the implementation. GraphQL exposes a single endpoint (`/graphql`) as opposed to REST's multiple resource endpoints.

## When to Apply
- UIs with diverse data needs where different clients (mobile, web) need different shapes of the same data
- Systems where reducing network round trips is important — GraphQL fetches nested relationships in one query
- BFF (Backend for Frontend) layer aggregating multiple microservices into a single client-optimized API
- Developer portals and internal tools where self-documenting schema introspection is valuable

## When Not to Apply
- Simple CRUD APIs where REST semantics are a natural fit
- File uploads and binary data (GraphQL multipart handling is cumbersome)
- Systems with strict HTTP caching requirements — GraphQL's single POST endpoint is not natively cacheable
- Teams without GraphQL expertise — REST is simpler and more familiar

## Key Concepts
- **Schema Definition Language (SDL)**: GraphQL types, queries, mutations, and subscriptions defined in SDL — the contract between server and client
- **Query**: A read operation — clients specify exactly which fields to return, including nested relationships
- **Mutation**: A write operation — create, update, delete. Returns the modified resource
- **Subscription**: A real-time event stream over WebSocket — clients subscribe to changes
- **Resolver**: The function that fulfills a field — resolvers can call databases, other services, or compute values
- **N+1 Problem**: Without optimization, nested resolvers trigger N additional queries for N parent items. Solved by **DataLoader** — batches and caches resolver calls within a single request
- **Federation**: Apollo Federation allows multiple services to contribute types to a unified GraphQL schema — each service owns a subgraph; the gateway composes them
- **Introspection**: Clients can query the schema itself — enables self-documenting APIs and tooling like GraphiQL
- **Apollo Server / Strawberry (Python) / Hot Chocolate (.NET)**: Popular GraphQL server implementations

## In Practice
Method uses GraphQL for BFF layers in React applications with complex data requirements. Apollo Server with Apollo Federation for microservices. DataLoader is always used to solve the N+1 problem. Schema-first design: SDL is written before resolvers. Persisted queries in production to prevent schema abuse and enable caching.

## Engineering Knowledge
💡 **Engineering Knowledge — GraphQL**: Clients ask for exactly what they need — no over-fetching or under-fetching. One endpoint, strongly typed schema, introspectable. Excellent for BFF layers and mobile apps with diverse data needs. Watch for the N+1 problem in resolvers — always use DataLoader for batched loading. Single POST endpoint breaks HTTP caching — use persisted queries or Apollo's APQ. Federation lets multiple microservices compose into one graph. Not a replacement for REST everywhere — choose based on the interaction model. → `engineering-knowledge-repository/api-design/graphql.md`

## Related Entries
- [REST Constraints](rest-constraints.md) — GraphQL is an alternative to REST for query-oriented APIs
- [gRPC](grpc.md) — gRPC is the alternative for performance-critical service-to-service APIs
- [API First Design](api-first-design.md) — schema-first development is GraphQL's version of API-first
- [OpenAPI Specification](openapi-specification.md) — OpenAPI documents REST APIs; GraphQL SDL documents GraphQL APIs
