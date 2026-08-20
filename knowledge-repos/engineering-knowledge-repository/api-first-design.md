---
id: api-first-design
tags: [methodology, api-design, backend]
surfaces-at: [application-design, functional-design, requirements-analysis]
related: [openapi-specification, rest-constraints, graphql, api-versioning, api-deprecation]
complexity: foundational
---

# API First Design

## What It Is
A development philosophy where the API contract is designed and agreed upon before any implementation begins. The API specification becomes the source of truth — frontend, backend, and QA teams can work in parallel against the spec rather than sequentially waiting for implementation. API-first produces clearer contracts, reduces integration friction, and forces design decisions to happen during planning rather than during implementation.

## When to Apply
- New services with consumers (frontend teams, partner integrations, third-party clients)
- Microservices with inter-service dependencies — teams can develop against mock servers while the provider is built
- Any project where multiple teams need to collaborate on an API

## When Not to Apply
- Exploratory prototypes where the API shape is highly uncertain — heavy spec work on a throwaway prototype wastes time
- Internal scripts and tooling with no external consumers

## Key Concepts
- **Design Before Code**: The API contract (OpenAPI spec, GraphQL schema, `.proto` file) is the first deliverable — reviewed and approved before a line of implementation is written
- **Mock Servers**: Contract-first enables mock servers (Prism, Mockoon) generated from the spec — consumers can integrate immediately without waiting for the real implementation
- **Parallel Development**: Frontend and backend teams work concurrently — frontend against mock, backend against spec. Integration happens late but is low-risk because both sides match the contract
- **API Review Gate**: A formal or lightweight review of the API design before implementation — checks for consistency, usability, versioning, error handling. Cheaper to change a spec than code
- **Consumer-Driven Contracts (CDC)**: The consumer writes the contract they need; the provider verifies they fulfill it. Pact is the leading CDC framework. Complementary to API-first
- **Design System Consistency**: API-first enforces naming conventions, pagination patterns, error response standards, and versioning strategy across all services — produces a coherent API landscape

## In Practice
Method's standard: write the OpenAPI spec in `api/openapi.yaml` during the Application Design stage. API review with the consuming team before development starts. Prism mock server deployed for consumer teams immediately. Backend and frontend develop in parallel. Contract tests verify implementation matches spec before each merge.

## Engineering Knowledge
💡 **Engineering Knowledge — API First Design**: Design the contract before writing any code. Write the OpenAPI spec, get it reviewed by consumers, spin up a Prism mock server — then frontend and backend develop in parallel. The integration risk is front-loaded into the design phase where changes are cheap. API review catches naming inconsistencies, missing error codes, and versioning gaps before they're baked into code. This is especially high-value when multiple teams share a service boundary. → `engineering-knowledge-repository/api-design/api-first-design.md`

## Related Entries
- [OpenAPI Specification](openapi-specification.md) — OpenAPI is the artifact produced in API-first design
- [REST Constraints](rest-constraints.md) — REST is the most common style for API-first design
- [GraphQL](graphql.md) — schema-first is GraphQL's equivalent of API-first
- [API Versioning](api-versioning.md) — versioning strategy decisions belong in the API design phase
