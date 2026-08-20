---
id: consumer-driven-contract-testing
tags: [methodology, testing, api-design, distributed-systems, microservices]
surfaces-at: [application-design, code-generation]
related: [contract-testing, api-first-design, openapi-specification, microservices, continuous-integration]
complexity: intermediate
---

# Consumer-Driven Contract Testing

## What It Is
A testing approach where the consumer of an API defines the contract — the specific requests it makes and the response shape it expects — and the provider verifies it satisfies that contract in CI. Unlike provider-driven contracts (OpenAPI specs written by the provider), consumer-driven contracts capture what consumers actually use, not everything the API offers. Pact is the dominant framework. The key insight: providers can safely make changes as long as they don't break any consumer's recorded expectations.

## When to Apply
- Microservices architectures where multiple services call each other and integration tests are slow or fragile
- When you want to decouple provider and consumer release cycles — providers can deploy independently if contracts pass
- As a faster, more targeted alternative to full integration test environments for verifying API compatibility

## When Not to Apply
- Monoliths or co-deployed systems where integration tests are fast and reliable
- Public APIs with many unknown consumers — you cannot collect contracts from consumers you don't control
- Teams without the discipline to keep contracts up to date — stale contracts provide false confidence

## Key Concepts
- **Consumer**: The service that calls the API — writes the contract specifying what it sends and what it expects back
- **Provider**: The service that implements the API — verifies it satisfies all consumer contracts in its CI pipeline
- **Pact**: The leading consumer-driven contract testing framework. Consumer tests generate a `.pact` JSON file describing interactions. Provider tests replay those interactions against the real provider
- **Pact Broker**: A central server that stores and shares pact files between consumer and provider CI pipelines. `can-i-deploy` queries tell you if a version is safe to deploy
- **`can-i-deploy`**: A Pact Broker CLI tool — "can this version of service A be deployed given the current deployed versions of its dependencies?" Enables safe independent deployments
- **Interaction**: A single consumer-provider exchange — a specific request and the expected response shape. Consumers only specify the fields they actually use — not the full response
- **Provider States**: Setup hooks that put the provider in the correct state before verifying an interaction — e.g., "a user with ID 123 exists"
- **vs. OpenAPI Contract Testing**: OpenAPI tests verify the provider matches its spec. Consumer-driven contracts verify the provider satisfies specific consumer needs. They are complementary — OpenAPI for completeness, Pact for consumer-specific safety

## In Practice
Method uses Pact for service-to-service contract testing in microservices deployments. Consumer teams write Pact tests alongside their service code. Pact files are published to a Pact Broker on every CI run. Provider CI runs verification against all consumer contracts before merge. `can-i-deploy` gates production deployments. This replaces fragile shared integration environments for inter-service compatibility verification.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Consumer-Driven Contract Testing**: Providers break consumers silently — integration environments catch it late. Pact solves this: consumers record what they actually use; providers verify they still satisfy it in CI. The `can-i-deploy` check answers "is it safe to release this version?" without a shared environment. Consumer contracts only specify the fields the consumer uses — providers can add fields freely. Provider states set up the test scenario. Run verification on every provider PR. Pact Broker stores contracts and tracks compatibility across versions. → `engineering-knowledge-repository/consumer-driven-contract-testing.md`

## Related Entries
- [Contract Testing](contract-testing.md) — the broader category; consumer-driven is the specific approach
- [API First Design](api-first-design.md) — consumer-driven contracts are the test-layer enforcement of API-first agreements
- [OpenAPI Specification](openapi-specification.md) — complementary: OpenAPI documents completeness; Pact verifies consumer-specific correctness
- [Microservices](microservices.md) — consumer-driven contracts are most valuable in microservices where inter-service coupling is highest
- [Continuous Integration](continuous-integration.md) — contract verification runs in both consumer and provider CI pipelines
