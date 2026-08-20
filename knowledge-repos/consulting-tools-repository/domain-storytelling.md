---
id: domain-storytelling
tags: [ddd, discovery, facilitation, architecture]
surfaces-at: [requirements-analysis, application-design]
related: [event-storming, core-domain-chart, domain-message-flow-modelling, listening-tours, contextual-inquiry, service-blueprinting]
complexity: intermediate
---

# Domain Storytelling

## What It Is
A collaborative modelling technique in which domain experts tell stories about how they do their work, and facilitators capture those stories in a structured pictographic language. Developed by Stefan Hofer and Henning Schwentner. Each story is told in the first person ("I do X with Y, then send Z to…") and captured as a diagram of actors, work objects, and activities. The output is a series of domain stories that collectively describe how a business domain operates — in business language, before any technical framing is applied. Domain Storytelling is referenced throughout Nick Tune's *Architecture Modernization* as a primary technique for surfacing domain knowledge before architectural decisions are made.

## When to Use
- To understand a domain before designing bounded contexts or service boundaries
- When domain experts and engineers have difficulty communicating — Domain Storytelling provides a shared visual language
- Early in Requirements Analysis to surface business processes without immediately jumping to system design
- As an alternative or complement to Event Storming — Domain Storytelling works better for structured, well-understood processes; Event Storming works better for complex, exploratory domains
- When User Stories have been written without deep domain understanding — Domain Stories are the raw material User Stories should be derived from
- In modernization engagements, to understand the legacy system's business logic before reverse engineering the code

## Key Concepts
- **Pictographic language**: Domain stories are captured as simple diagrams with a defined notation — actors (people or systems, drawn as icons), work objects (documents, data, physical objects), and activities (what the actor does with the work object). Arrows connect them. The notation is intentionally simple so non-technical participants can read and correct it.
- **Granularity levels**: Stories can be told at different granularity — a high-level story shows the whole domain; a detailed story zooms into a specific process. Facilitators choose granularity based on what decisions the stories need to inform.
- **Pure domain language**: Technical implementation details are explicitly excluded from Domain Stories. "The system processes the claim" is wrong — "Maria reviews the claim and approves or escalates it" is right. The goal is to capture how the business works, not how software currently implements it.
- **Scenarios**: Multiple stories cover different scenarios — the normal case, exception paths, edge cases. Each scenario produces a separate diagram. The collection of stories across scenarios is more valuable than any single story.
- **Domain Storytelling vs. Event Storming**: Event Storming uses sticky notes, is non-linear, and is better for exploring complex, unknown domains. Domain Storytelling uses structured diagrams, is narrative, and is better for understanding well-defined processes. Both surface domain knowledge; they complement each other.
- **Domain boundaries emerge**: When actors in different stories are doing incompatible things with the same work object, or when actors use different vocabulary for the same concept, domain boundaries become visible. These are often where bounded context boundaries should be drawn.

## Method Application
Domain Storytelling is used during Requirements Analysis and Application Design. During Requirements Analysis, it surfaces business domain knowledge that informs requirements completeness. During Application Design, stories from different actors are compared to identify where bounded context boundaries should be drawn and what messages flow between them. The technique is also useful during Reverse Engineering of brownfield systems — asking "how does this business process work?" before "how does the code work?" produces better reverse engineering outcomes.

## Consulting Insight
🎯 **Consulting Tool — Domain Storytelling**: The most valuable thing Domain Storytelling does is prevent the most common requirements failure: building what the system currently does instead of what the business actually needs. When teams skip domain storytelling and go directly to technical analysis, they tend to replicate the existing system's quirks and workarounds rather than discovering the underlying business intent. Domain Storytelling forces the conversation back to first principles — "what are you actually trying to do?" — before any technical solution is proposed. → `consulting-tools-repository/domain-storytelling.md`

## Related Entries
- [Event Storming](event-storming.md) — complementary technique; Event Storming is exploratory and non-linear; Domain Storytelling is narrative and structured
- [Core Domain Chart](core-domain-chart.md) — domain stories are raw material for classifying domains as Core, Supporting, or Generic
- [Domain Message Flow Modelling](domain-message-flow-modelling.md) — downstream: stories identify the messages that flow between domains
- [Listening and Mapping Tours](listening-tours.md) — upstream: listening tours identify which domains to story-tell; Domain Storytelling goes deeper into specific domains
- [Contextual Inquiry](contextual-inquiry.md) — related field research technique; Contextual Inquiry observes work in context; Domain Storytelling reconstructs work through narrative
- [Service Blueprinting](service-blueprinting.md) — complementary: Service Blueprinting maps the full service including frontstage/backstage; Domain Storytelling focuses on business domain processes
