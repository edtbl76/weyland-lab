---
id: state
tags: [pattern, backend]
surfaces-at: [functional-design, code-generation]
related: [strategy-pattern, command-pattern, memento]
complexity: intermediate
---

# State Pattern

## What It Is
A behavioral pattern that allows an object to alter its behavior when its internal state changes. The object will appear to change its class. Instead of large conditional blocks (`if state == X do this; else if state == Y do that`), each state is encapsulated in a separate class, and the context delegates behavior to the current state object.

## When to Apply
- An object's behavior depends on its state and must change at runtime
- Operations have large, multipart conditional statements that depend on the object's state — each branch in the conditional can be refactored into a state class
- Domain objects with explicit lifecycle states: Orders (Pending → Confirmed → Shipped → Delivered → Cancelled), Payments (Initiated → Authorized → Captured → Refunded), Workflows
- Finite state machines in game entities, protocol handlers, vending machines, UI components

## When Not to Apply
- Simple two-state objects where an `if/else` is clear and sufficient
- When states are added frequently and the overhead of new classes per state is burdensome
- When the state machine is better expressed as a state machine library or configuration rather than code

## Key Concepts
- **Context**: The object whose behavior changes — holds a reference to the current State object and delegates requests to it
- **State Interface**: Declares the interface that all concrete states must implement
- **Concrete State**: Implements behavior associated with a specific state of the Context; may trigger state transitions by replacing the Context's current state
- **State Transitions**: States can trigger their own transitions (tell the Context to switch to a different state)
- **Replacing Conditionals**: The key refactoring — each `case` in a large switch/if-else becomes a Concrete State class

## In Practice
State is the canonical refactoring for bloated entity lifecycle logic. In Method engagements, Order, Payment, Subscription, and Booking domain objects frequently accumulate conditional logic keyed on status — the State pattern extracts each lifecycle phase into its own class. Modern tools like XState (JavaScript) and stateless (.NET) provide State pattern infrastructure with explicit transition declarations, event handling, and guard conditions.

## Engineering Knowledge
💡 **Engineering Knowledge — State Pattern**: When an object's behavior depends on its lifecycle state and you find yourself writing `if status == 'pending' ... else if status == 'confirmed' ...`, that's a State pattern waiting to happen. Encapsulate each state in its own class; the object delegates to its current state. Order, Payment, Subscription lifecycle is the canonical application. For complex state machines, consider XState or stateless rather than raw State pattern classes. → `engineering-knowledge-repository/design-patterns/state.md`

## Related Entries
- [Strategy Pattern](strategy-pattern.md) — Strategy and State are structurally identical; Strategy algorithms are selected by the client, State transitions happen based on internal logic
- [Command Pattern](command-pattern.md) — Commands often trigger State transitions
- [Memento Pattern](memento.md) — Memento can capture State context for undo
