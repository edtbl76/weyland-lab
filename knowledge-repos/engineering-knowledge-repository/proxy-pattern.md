---
id: proxy-pattern
tags: [pattern, backend, frontend]
surfaces-at: [functional-design, code-generation]
related: [decorator, dependency-injection]
complexity: intermediate
---

# Proxy Pattern

## What It Is
A structural design pattern that provides a substitute or placeholder for another object. The proxy controls access to the real object, intercepting calls to perform additional logic — lazy initialization, access control, logging, caching, or remote delegation — before forwarding to the real subject. The proxy implements the same interface as the real subject, making it transparent to clients.

## When to Apply
- **Virtual Proxy**: Defer expensive object creation until first use (lazy initialization)
- **Protection Proxy**: Add access control checks before delegating to the real object
- **Remote Proxy**: Represent an object in a different address space — a local stand-in for a network service
- **Caching Proxy**: Cache results of expensive operations on the real object
- **Logging/Monitoring Proxy**: Record calls to the real object without modifying it

## Key Concepts
- **Same Interface**: The proxy and the real subject implement the same interface — clients interact with the proxy without knowing it's not the real object
- **Delegation**: The proxy holds a reference to the real subject and delegates calls after applying its own logic
- **Proxy vs. Decorator**: Decorators add behavior; proxies control access. The distinction is intent — both use the same wrapping structure. A proxy manages the lifecycle or access to the subject; a decorator enhances the subject's behavior
- **Java Dynamic Proxies / Python `__getattr__`**: Runtime proxy generation without explicit implementation — the proxy intercepts all method calls dynamically
- **ORM Lazy Loading**: Database ORM entities commonly use virtual proxies — related objects are placeholder proxies until accessed, deferring the database query
- **Service Mesh Sidecar Proxies**: Envoy/Istio sidecar proxies are a distributed systems application of this pattern — intercepting network calls for observability, auth, and retry without application code changes

## In Practice
Method uses proxy objects for lazy-loaded ORM relationships and for wrapping external API clients with circuit breaker logic. Python's `unittest.mock.MagicMock` is a proxy for testing. Infrastructure-level proxies (Envoy) handle service mesh concerns outside application code.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Proxy Pattern**: Use proxies to add access control, lazy loading, caching, or remote transparency without modifying the real object. The distinction from Decorator: proxies control access and lifecycle; decorators add behavior. ORM lazy loading, API client wrappers with retry/circuit-breaker, and sidecar proxies in service meshes are all practical applications. For test doubles, proxy objects (mocks) are the mechanism. → `engineering-knowledge-repository/proxy-pattern.md`

## Related Entries
- [Decorator](decorator.md) — decorator adds behavior; proxy controls access — structurally similar, different intent
- [Dependency Injection](dependency-injection.md) — DI injects either the real subject or a proxy transparently
