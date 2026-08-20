---
id: openapi-specification
tags: [tooling, api-design, backend, protocol]
surfaces-at: [application-design, functional-design, code-generation]
related: [rest-constraints, api-versioning, api-first-design, api-deprecation]
complexity: foundational
---

# OpenAPI Specification

## What It Is
A vendor-neutral, language-agnostic standard for describing REST APIs in a machine-readable format (YAML or JSON). OpenAPI (formerly Swagger) defines endpoints, request/response schemas, authentication, and error codes in a structured document that enables automatic documentation generation, client SDK generation, mock server creation, and contract testing. The specification is maintained by the OpenAPI Initiative (Linux Foundation).

## When to Apply
- All REST APIs — OpenAPI is the standard for REST API documentation
- API-first development — write the spec before writing code
- Any API consumed by external teams or systems where a formal contract is needed
- When generating client SDKs for multiple languages

## Key Concepts
- **OpenAPI Document**: A YAML or JSON file describing the complete API — paths, operations, parameters, request/response bodies, authentication schemes
- **Swagger UI / Redoc**: Tools that render OpenAPI documents as interactive HTML documentation — engineers can read and try the API in the browser
- **Code Generation**: Tools like `openapi-generator` produce client SDKs, server stubs, and typed models from an OpenAPI document in virtually any language
- **Schema Object**: JSON Schema-based type definitions for request/response bodies — defines field names, types, required fields, validation constraints
- **$ref**: Reference to a reusable schema component — avoids repetition, enables schema libraries
- **Operation ID**: A unique identifier for each operation — used in code generation and SDK method naming
- **`info.version`**: The API version documented in this spec file — should align with the API versioning strategy
- **Spec-First vs. Code-First**: Spec-first — write OpenAPI before implementing. Code-first — generate OpenAPI from code annotations (SpringDoc, Swashbuckle). Spec-first enables API-first design; code-first may produce lower-quality contracts
- **Contract Testing**: Use the OpenAPI spec as the source of truth for contract tests — verify that the implementation matches the documented contract (Dredd, Schemathesis)

## In Practice
Method uses OpenAPI 3.x for all REST API documentation. Spec-first development for new services — the OpenAPI document is reviewed and approved before implementation begins. `openapi-generator` generates TypeScript API clients for frontends. Swagger UI is deployed as part of the service in non-production environments. The spec file lives in the service repository at `api/openapi.yaml`.

## Engineering Knowledge
💡 **Engineering Knowledge — OpenAPI Specification**: Write the OpenAPI spec before you write the code. It's the contract — review and approve it first, then implement against it. Use `openapi-generator` to produce typed clients for frontends — eliminates handwritten API client code. Deploy Swagger UI for developer convenience (non-prod). Store `api/openapi.yaml` in the service repository. Use $ref components for reusable schemas. Run Schemathesis or Dredd in CI to verify the implementation matches the spec. → `engineering-knowledge-repository/api-design/openapi-specification.md`

## Related Entries
- [REST Constraints](rest-constraints.md) — OpenAPI documents REST API contracts
- [API Versioning](api-versioning.md) — each API version has its own OpenAPI document
- [API First Design](api-first-design.md) — OpenAPI spec is the artifact produced in API-first design
- [API Deprecation](api-deprecation.md) — OpenAPI `deprecated: true` marks operations for deprecation
