---
id: proxy
tags: [pattern, backend, network]
surfaces-at: [functional-design, code-generation, application-design]
related: [decorator-pattern, facade-pattern, adapter-pattern]
complexity: intermediate
---

# Proxy Pattern

## What It Is
A structural pattern that provides a surrogate or placeholder for another object to control access to it. The proxy implements the same interface as the real object and intercepts calls, adding behavior (access control, logging, lazy initialization, caching, remote communication) before or after delegating to the real object.

## When to Apply
- **Virtual Proxy**: Delay expensive object creation until it's actually needed (lazy initialization)
- **Protection Proxy**: Control access to the real object based on permissions
- **Remote Proxy**: Represent an object in a different address space (RPC, gRPC stub, HTTP client)
- **Caching Proxy**: Cache results of expensive operations on the real object
- **Logging/Monitoring Proxy**: Transparently add logging or metrics around method calls

## When Not to Apply
- When the added indirection introduces unacceptable latency
- When the same result can be achieved more simply with a Decorator or direct code change
- When the proxy interface diverges from the subject — use Adapter or Facade instead

## Key Concepts
- **Subject Interface**: The common interface implemented by both the Proxy and the Real Subject
- **Real Subject**: The actual object that does the real work
- **Proxy**: Holds a reference to the Real Subject, implements the Subject interface, and controls access
- **Transparency**: Clients shouldn't need to know whether they're talking to a proxy or the real object
- **AOP (Aspect-Oriented Programming)**: Runtime proxies are the mechanism behind AOP frameworks (Spring AOP, Castle DynamicProxy) — method interceptors are dynamically generated proxies

## In Practice
Proxy is ubiquitous in frameworks: Spring's `@Transactional` and `@Cacheable` annotations work through dynamic proxies; JPA lazy-loaded relationships use virtual proxies; gRPC generated stubs are remote proxies. In Method engagements, the most common explicit use is Protection Proxy for authorization and Caching Proxy for read-heavy APIs. Decorator adds behavior by wrapping; Proxy controls access — the structural form is identical but the intent differs.

## Engineering Knowledge
💡 **Engineering Knowledge — Proxy Pattern**: A proxy stands in front of a real object to control access — lazy-load it, cache its responses, check permissions, or add logging. Structurally identical to Decorator, but the intent is access control vs. behavior addition. Most framework magic (Spring transactions, JPA lazy loading, gRPC stubs) is implemented as runtime-generated proxies under the hood. → `engineering-knowledge-repository/design-patterns/proxy.md`

## Related Entries
- [Decorator Pattern](decorator-pattern.md) — Decorator adds behavior; Proxy controls access. Structurally the same, different intent.
- [Facade Pattern](facade-pattern.md) — Facade simplifies a complex interface; Proxy wraps a single object
- [Adapter Pattern](adapter-pattern.md) — Adapter changes the interface; Proxy preserves it
