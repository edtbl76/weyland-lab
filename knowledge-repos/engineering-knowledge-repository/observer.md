---
id: observer
tags: [pattern, backend, frontend]
surfaces-at: [functional-design, code-generation]
related: [hook-pattern, decorator, strategy, event-driven-architecture, pub-sub]
complexity: intermediate
---

# Observer Pattern

## What It Is
A behavioral design pattern where an object (the subject/observable) maintains a list of dependents (observers) and notifies them automatically when its state changes. Decouples the subject from its observers — the subject doesn't need to know who is watching or what they do with the notification. The foundation for event handling systems, reactive programming, and publish-subscribe architectures.

## When to Apply
- When a change in one object requires notifying others without tight coupling
- Implementing event systems, callbacks, or reactive state
- When the set of dependent objects is dynamic or unknown at design time
- Cross-cutting state changes that multiple independent components need to react to

## Key Concepts
- **Subject (Observable)**: Maintains a list of observers; provides `subscribe()`, `unsubscribe()`, and `notify()` methods. Calls `notify()` when state changes
- **Observer**: Implements an `update()` or callback interface invoked by the subject on state change
- **Loose Coupling**: The subject only knows that observers implement the observer interface — not their concrete types or behavior
- **Push vs. Pull**: Push — subject sends state data in the notification. Pull — subject sends only a change notification; observers query the subject for current state. Pull is more flexible; push is more efficient when observers always need the same data
- **Memory Leaks**: Observers that are not unsubscribed hold a reference preventing garbage collection. Weak references or explicit cleanup (`unsubscribe()` in `componentWillUnmount`) are required
- **Java `Observable` / `EventListener`**: Built-in observer infrastructure. JavaScript `EventEmitter`, `addEventListener`. Python's `blinker` library. RxJS Observables (reactive extension of this pattern)
- **Reactive Programming**: RxJS, RxJava, Reactor — treat events as streams of data that observers can transform, filter, and combine. A powerful extension of the observer pattern
- **Event Bus**: A centralized event channel that decouples publishers and subscribers — all observers subscribe to a bus rather than to the subject directly

## In Practice
Method frontends use React state and context (pull-based observer pattern) and RxJS Observables for asynchronous event streams. Backend services use event buses (Spring ApplicationEventPublisher, Python's blinker) for internal domain events. Integration with external systems uses message queues (SNS, Kafka) — pub-sub at the infrastructure level.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Observer Pattern**: Use observers to decouple state change producers from consumers — subjects don't know who is watching. Always provide an unsubscribe mechanism and call it on cleanup to prevent memory leaks. For complex event streams, RxJS/Reactor give you filtering, transformation, and backpressure on top of basic observer semantics. At the infrastructure level, message queues (Kafka, SNS/SQS) are the observer pattern at scale. → `engineering-knowledge-repository/observer.md`

## Related Entries
- [Hook Pattern](hook-pattern.md) — hooks and observers both inject behavior at defined points without tight coupling
- [Decorator](decorator.md) — decorator wraps behavior around a single object; observer distributes change notifications to many
- [Strategy](strategy.md) — strategy swaps algorithm implementations; observer distributes change notifications
- [Event-Driven Architecture](event-driven-architecture.md) — architectural application of the observer pattern at service scale
- [Pub-Sub](pub-sub.md) — publish-subscribe is the distributed, decoupled form of the observer pattern
