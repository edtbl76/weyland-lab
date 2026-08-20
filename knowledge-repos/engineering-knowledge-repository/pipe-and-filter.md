---
id: pipe-and-filter
tags: [pattern, backend]
surfaces-at: [application-design, functional-design, infrastructure-design]
related: [event-driven-architecture, chain-of-responsibility, choreography-vs-orchestration]
complexity: foundational
---

# Pipe and Filter Architecture

## What It Is
An architectural style where data flows through a sequence of processing steps (filters) connected by channels (pipes). Each filter receives input, transforms or processes it, and sends the result to the next filter. Filters are independent — they don't know about each other — and can be composed, reordered, and reused. The Unix shell (combining `cat | grep | sort | uniq`) is the canonical example.

## When to Apply
- Data transformation and processing pipelines: ETL, log processing, image/video processing, document conversion
- Systems where processing steps are independent, reusable, and composable
- Stream processing architectures where data flows continuously through transformation stages
- When the same data may need different processing paths (configurable filter chains)

## When Not to Apply
- Interactive applications with complex bidirectional state — pipe-and-filter is fundamentally unidirectional
- When filters need to share significant state with each other — breaks filter independence
- Simple one-step transforms where the pattern adds ceremony without benefit

## Key Concepts
- **Filter**: An independent processing component — reads from input, transforms, writes to output. Stateless or self-contained state.
- **Pipe**: The connector between filters — a channel, queue, or stream that transports data
- **Data Source**: The origin of the data stream — file, API, event queue
- **Data Sink**: The terminal destination — database, file, another system
- **Independence**: Filters know nothing about other filters — they only know about their input format and output format
- **Composability**: Filters can be reordered, replaced, or combined to create new pipelines
- **Push vs. Pull**: Filters can either pull from upstream or be pushed to by upstream — streaming frameworks support both

## In Practice
Pipe-and-filter is the architecture of ETL pipelines, CI/CD pipelines, stream processing with Apache Kafka Streams or AWS Step Functions, and data transformation workflows. In Method engagements, it appears most in data integration work and event stream processing. Spring Integration, Apache Camel, and AWS EventBridge Pipes are framework-level implementations. Chain of Responsibility is pipe-and-filter at the method/middleware level.

## Engineering Knowledge
💡 **Engineering Knowledge — Pipe and Filter**: Build data processing as a sequence of independent, composable filters connected by pipes. Each filter transforms its input and passes it on — no filter needs to know about the others. Unix shell pipes are the purest example; Kafka Streams, AWS Step Functions, and Spring Integration implement the same pattern at scale. Reorder, replace, or add filters without touching the rest of the pipeline. → `engineering-knowledge-repository/architectural-styles/pipe-and-filter.md`

## Related Entries
- [Event-Driven Architecture](event-driven-architecture.md) — event streams are the modern pipe in event-driven pipe-and-filter systems
- [Chain of Responsibility](../design-patterns/chain-of-responsibility.md) — Chain of Responsibility is pipe-and-filter at the object/middleware level
