---
id: actor-model
tags: [pattern, concurrency, distributed-systems, backend]
surfaces-at: [application-design, functional-design]
related: [async-programming-patterns, reactor-pattern, message-queues, event-driven-architecture, race-conditions]
complexity: advanced
---

# Actor Model

## What It Is
A concurrency model where the fundamental unit of computation is an actor — an independent entity with its own private state, a mailbox for receiving messages, and behavior defined by how it processes messages. Actors communicate exclusively by sending asynchronous messages; they never share memory directly. This eliminates entire classes of concurrency bugs (race conditions, deadlocks from shared state) by design. The actor model scales naturally from a single machine to a distributed cluster — actors can be local or remote, and the messaging interface is identical.

## When to Apply
- Highly concurrent stateful systems where shared-memory concurrency is complex to reason about
- Distributed systems where actors need to span multiple nodes transparently
- Systems requiring location transparency — code doesn't care whether an actor is local or remote
- Fault-tolerant systems leveraging supervision hierarchies (Erlang/Akka's "let it crash" philosophy)

## Key Concepts
- **Actor**: Has three capabilities: send messages to other actors, create new actors, determine behavior for the next message (update internal state). Each actor processes messages sequentially from its mailbox — no concurrency within a single actor
- **Mailbox**: A queue of incoming messages. The actor processes one message at a time, so its internal state is always accessed by exactly one thread. No locks required for actor-internal state
- **Message Passing**: All communication is asynchronous and by value (or immutable reference). No shared mutable state between actors — the message is the interface. Fire-and-forget semantics by default; request-response patterns are built on top
- **Supervision Hierarchies**: Actors form trees. Parent actors supervise children — when a child actor fails (throws an exception), the parent decides: restart it, stop it, escalate to its own parent, or resume. Erlang's "let it crash" philosophy — don't defensively handle every error; let the supervisor restart the actor in a clean state
- **Location Transparency**: Sending a message to an actor looks the same whether the actor is in the same process or on a remote machine. The actor system handles routing — enables seamless distribution
- **Akka (JVM)**: The dominant actor framework for Java/Scala. Akka Typed enforces message type safety. Akka Cluster for distributed actor systems. Akka Streams for reactive stream processing
- **Erlang/Elixir OTP**: The origin of the modern actor model. Erlang's BEAM VM is purpose-built for actors — millions of lightweight processes, hot code reloading, battle-tested fault tolerance. Phoenix/Elixir for web; OTP GenServer is the standard actor abstraction
- **Python**: `pykka`, `dramatiq` (task-based). Less mature ecosystem than JVM or Erlang
- **Actor vs. Thread**: Actors are cheaper than threads — millions can exist concurrently. The actor system schedules actors across a thread pool. Actors provide higher-level abstractions (supervision, location transparency) that threads don't

## In Practice
Method uses Akka Typed for JVM services with complex stateful concurrency requirements and Elixir/Phoenix for real-time communication features leveraging OTP's supervision and fault tolerance. The actor model is not applied universally — for stateless request-handling services, async/await is simpler and sufficient.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Actor Model**: Actors eliminate shared-memory concurrency bugs by design — each actor's state is private and accessed sequentially. The supervision hierarchy is the killer feature: define how failures are handled structurally, not with try/catch everywhere. Use Akka Typed for JVM; Elixir/OTP for maximum fault tolerance and hot-reloading. Don't reach for actors when async/await suffices — actors add conceptual overhead. The right use cases are complex stateful concurrency, distributed systems needing location transparency, and systems where fault isolation and automatic recovery are core requirements. → `engineering-knowledge-repository/actor-model.md`

## Related Entries
- [Async Programming Patterns](async-programming-patterns.md) — async/await is the lighter-weight alternative to actors for I/O-bound concurrency
- [Reactor Pattern](reactor-pattern.md) — the reactor pattern handles I/O event dispatch; the actor model handles stateful concurrent computation
- [Message Queues](message-queues.md) — actor mailboxes are conceptually similar to message queues; at scale, actors integrate with external message queues
- [Event-Driven Architecture](event-driven-architecture.md) — actor systems and event-driven architectures share asynchronous message-passing foundations
- [Race Conditions](race-conditions.md) — actors eliminate shared-memory race conditions by confining state to individual actors
