---
id: law-of-demeter
tags: [principle, backend]
surfaces-at: [functional-design, code-generation]
related: [solid-principles, separation-of-concerns, dry-principle]
complexity: foundational
---

# Law of Demeter (Principle of Least Knowledge)

## What It Is
A design guideline for object-oriented software: a method should only call methods on objects it directly knows about — its own fields, its parameters, objects it creates, and global objects. A method should not "reach through" an object to call methods on the objects it returns. The shorthand: "talk to friends, not strangers." Violations produce "train wreck" code: `order.getCustomer().getAddress().getCity()`.

## When to Apply
- Reviewing method implementations that chain through multiple objects
- Designing object interfaces — ask whether callers need to reach into internals
- When refactoring code that has high coupling between distant objects
- When adding methods to domain objects — ask what the object should expose vs. what it should encapsulate

## When Not to Apply
- **Fluent interfaces and builder chains** (e.g., query builders, stream operations) are intentional chains and don't violate Demeter in spirit — they're chaining on the same object or a sequence of transforms
- **Data transfer objects (DTOs)** and value objects are often accessed in chains — this is intentional; DTOs exist to be read
- In functional pipelines where the chain is a sequence of transformations, not reaching into object internals

## Key Concepts
- **Talk to Friends**: A method may call methods on: (1) itself, (2) its own fields, (3) objects passed as parameters, (4) objects it creates locally, (5) global/static objects
- **Don't Talk to Strangers**: Don't call methods on objects returned by another method — those are strangers
- **Train Wreck**: `a.getB().getC().doSomething()` — each `.` is a dependency on the internal structure of the previous object
- **Tell, Don't Ask**: Related principle — tell objects to do things rather than asking for data and doing it yourself. Pull behavior toward data.
- **Move the Method**: The fix for a Demeter violation is often to move the method closer to the data it needs

## In Practice
Law of Demeter violations are a reliable signal of Feature Envy (a code smell where a method is more interested in another class's data than its own). The fix is usually to move behavior to the class that owns the data, or to add a method on the intermediate object that performs the needed operation — keeping navigation internal. In domain modeling, Demeter violations often indicate that a method belongs on a different aggregate or entity.

## Engineering Knowledge
💡 **Engineering Knowledge — Law of Demeter**: Don't write train wrecks: `order.getCustomer().getAddress().getCity()`. Each dot is a dependency on an internal structure you shouldn't know about. Talk to the objects you directly know; let them talk to their own internals. The fix is usually to move the operation to the object that owns the data (Tell, Don't Ask). Exceptions: fluent builders, DTOs, and functional pipelines don't violate the spirit of Demeter. → `engineering-knowledge-repository/architectural-philosophy/law-of-demeter.md`

## Related Entries
- [SOLID Principles](solid-principles.md) — Single Responsibility and Interface Segregation support Demeter by keeping objects focused
- [Separation of Concerns](separation-of-concerns.md) — SoC at the design level; Demeter at the method level
