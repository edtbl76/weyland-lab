---
id: chain-of-responsibility
tags: [pattern, backend]
surfaces-at: [functional-design, code-generation, application-design]
related: [command-pattern, decorator-pattern, strategy-pattern]
complexity: intermediate
---

# Chain of Responsibility Pattern

## What It Is
A behavioral pattern that passes a request along a chain of handlers. Each handler decides either to process the request or to pass it to the next handler in the chain. The sender doesn't know which handler will process the request — it's decoupled from the receiver. Handlers are linked dynamically and can be composed in different orders.

## When to Apply
- More than one object may handle a request and the handler is determined at runtime
- Issuing a request to multiple objects without specifying the receiver explicitly
- The set of handlers and their order should be configurable dynamically
- Middleware pipelines: HTTP request processing, logging pipelines, validation chains, event handling

## When Not to Apply
- When exactly one handler must always process the request — use a direct call instead
- Deep chains where the request bubbles through many handlers unnecessarily — can obscure flow and harm performance
- When the order of handlers is fixed and never changes — a simple sequence of calls is clearer

## Key Concepts
- **Handler Interface**: Declares the method for handling requests and optionally holding a reference to the next handler
- **Concrete Handler**: Processes requests it's responsible for; passes others to the next handler
- **Chain**: Assembled at runtime by linking handlers; the client sends to the first handler in the chain
- **Pass or Handle**: Each handler either processes the request and optionally stops propagation, or passes it on
- **Middleware**: The modern form of Chain of Responsibility — HTTP middleware stacks (Express, ASP.NET, Django) are chains where each middleware processes the request/response and calls `next()`

## In Practice
Chain of Responsibility is the pattern underlying every web framework's middleware stack. In Method engagements, it appears as: HTTP request pipelines (auth middleware → logging middleware → rate-limiting middleware → handler), validation chains (each validator checks one rule), and event processing pipelines. The pattern is implicit in most frameworks — recognizing it helps engineers reason about ordering effects and add custom middleware correctly.

## Engineering Knowledge
💡 **Engineering Knowledge — Chain of Responsibility**: Pass a request through a chain of handlers — each one decides to handle it or pass it on. This is the pattern behind every web middleware stack (Express, ASP.NET, Django): auth → logging → rate-limit → handler, all linked as a chain. Use it when multiple objects might handle a request and the handler should be determined at runtime. Watch for deep chains that obscure what's actually handling the request. → `engineering-knowledge-repository/design-patterns/chain-of-responsibility.md`

## Related Entries
- [Command Pattern](command-pattern.md) — Commands are often the request objects passed through a Chain of Responsibility
- [Decorator Pattern](decorator-pattern.md) — Decorator wraps to add behavior; Chain passes to delegates for handling
- [Strategy Pattern](strategy-pattern.md) — Strategy selects one algorithm; Chain may route through many handlers
