---
id: safe
tags: [delivery, organizational]
surfaces-at: [validated-intent, workflow-planning]
related: [iron-triangle, dependency-mapping, okrs, raci, organizational-design]
complexity: intermediate
---

# SAFe (Scaled Agile Framework)

## What It Is
A comprehensive framework for scaling agile practices across large organizations — enabling multiple agile teams to work in coordination on a shared product or program. Developed by Dean Leffingwell, SAFe provides roles, ceremonies, and artifacts that structure how teams plan, execute, and coordinate delivery at three levels: Team (individual agile teams), Program (Agile Release Train — multiple teams working toward a Program Increment), and Portfolio (investment themes, value streams, and strategic alignment). SAFe is the most widely adopted enterprise agile framework by market share, particularly in large organizations with regulatory requirements, complex dependencies, or waterfall legacy governance.

## When to Use
- Large programs requiring multiple agile teams working in coordinated delivery
- When a client has attempted team-level agile adoption but program-level coordination is failing
- Organizations that need to maintain some program-level predictability (budgets, release dates) while adopting agile principles
- When dependency management across teams is causing delivery failures
- Transformation programs that replace project-based governance with value stream-based continuous delivery

## Key Concepts
- **Agile Release Train (ART)**: The primary SAFe construct — a long-lived team of agile teams (typically 50-125 people) aligned to a value stream. The ART delivers a continuous flow of incremental value through Program Increments (PIs)
- **Program Increment (PI)**: An 8-12 week planning and delivery cycle. PI Planning is a two-day synchronization event where all teams in the ART plan their upcoming increment together — identifying features, dependencies, risks, and commitments
- **PI Planning**: The flagship SAFe ceremony. All teams plan in the same room (or virtual equivalent), dependencies are identified and negotiated, and a program board shows the delivery plan across teams. PI Planning replaces months of asynchronous project planning with two days of synchronized face-to-face work
- **Value Streams**: The sequence of steps an organization takes to deliver value to a customer. SAFe organizes teams around value streams rather than functions — ensuring the full capability to deliver a product outcome is within a single organizational unit
- **Portfolio SAFe**: The highest level — aligns strategy (investment themes, OKRs) to the value streams and ARTs that execute it. Lean Portfolio Management replaces project-based funding with value stream budgeting
- **Lean-Agile Principles**: SAFe is built on ten Lean-Agile principles including: take an economic view, apply systems thinking, assume variability, build incrementally, integrate learning cycles, decentralize decision-making
- **SAFe Criticism**: Common critiques — SAFe is too heavyweight and reintroduces waterfall-style planning under agile vocabulary; PI Planning creates false precision; the framework is too prescriptive for complex domains. Valid concerns — SAFe works best in Complicated domain delivery at scale, not Complex domain innovation
- **SAFe vs. LeSS**: Large-Scale Scrum (LeSS) is a simpler, more prescriptive alternative that scales Scrum directly without the additional layers. LeSS favors fewer rules and more organizational structural change; SAFe accommodates existing structures with more ceremony

## Method Application
Method works with SAFe in two contexts: helping organizations implement SAFe as part of a digital transformation program, and operating within a client's existing SAFe structure as a delivery partner. In both cases, the PI Planning ceremony is the primary coordination mechanism — Method's work must be represented on the program board and dependencies with client teams identified and committed.

## Consulting Insight
🎯 **Consulting Tool — SAFe**: SAFe's most valuable contribution is PI Planning — the ceremony that forces cross-team dependency identification in a time-boxed, face-to-face setting. Organizations that can't run PI Planning effectively (too many surprises, dependencies identified too late, commitment reliability too low) have a coordination problem, not a process problem. Before recommending SAFe adoption, assess whether the organization has the coordination maturity to make PI Planning productive — because if they don't, the ceremony becomes theater. → `consulting-tools-repository/safe.md`

## Related Entries
- [Iron Triangle](iron-triangle.md) — PI Planning makes the iron triangle explicit at the program level; what can the ART deliver within the PI's fixed schedule?
- [Dependency Mapping](dependency-mapping.md) — the program board in PI Planning is a visual dependency map; dependency mapping is core to SAFe execution
- [OKRs](okrs.md) — Portfolio SAFe Lean Portfolio Management should align to OKRs; PI objectives should connect to organizational Key Results
- [RACI](raci.md) — SAFe defines roles (Product Owner, Release Train Engineer, Business Owner); RACI clarifies decision rights within those roles in the client context
- [Organizational Design](organizational-design.md) — SAFe adoption requires organizational restructuring around value streams; organizational design is a prerequisite
