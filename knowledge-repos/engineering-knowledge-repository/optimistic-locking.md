---
id: optimistic-locking
tags: [pattern, data, database, backend, distributed-systems]
surfaces-at: [functional-design, application-design]
related: [conditional-requests, pessimistic-locking, database-indexing, cqrs, event-sourcing]
complexity: intermediate
---

# Optimistic Locking

## What It Is
A concurrency control strategy that assumes conflicts are rare and allows multiple transactions to proceed without locking, but detects and rejects conflicts at write time. Each record carries a version token (an integer version number or a hash). When a client reads a record and then attempts to update it, the update includes the version token it read. The database (or application) checks: if the version matches the current record, the update succeeds and increments the version; if it doesn't match, another writer got there first and the update is rejected. The client must re-read and retry.

## When to Apply
- Read-heavy workloads where conflicts are infrequent — optimistic locking has zero overhead on the read path
- Web APIs where a user reads data, makes changes, then submits — the window between read and write is long
- Distributed systems where holding a database lock across a network round trip is impractical
- Document stores and ORMs that have built-in version column support

## When Not to Apply
- High-contention scenarios where conflicts are frequent — repeated retries degrade performance and UX
- Short transactions where pessimistic locking holds locks briefly — pessimistic may be simpler
- When conflict detection is not actionable — if the client cannot meaningfully retry, detecting the conflict adds complexity with no benefit

## Key Concepts
- **Version Column**: An integer column (commonly `version` or `lock_version`) incremented on every update. The UPDATE statement includes `WHERE id = ? AND version = ?` — if zero rows are affected, a conflict occurred
- **Hash/ETag Version**: A hash of the record's content used as the version token — content-derived rather than sequence-based. Used in HTTP conditional requests (`ETag`/`If-Match`)
- **Lost Update Problem**: Without optimistic locking — User A reads record (v1), User B reads record (v1), User A writes (now v2), User B writes (overwrites v2 with stale data). Optimistic locking rejects User B's write
- **`@Version` in JPA/Hibernate**: Annotation on a version field — Hibernate automatically manages version checking and incrementing in UPDATE statements
- **Active Record `lock_version`**: Rails built-in optimistic locking — add a `lock_version` integer column and Rails handles the rest
- **Retry Logic**: On conflict, the client re-fetches the latest version, re-applies their changes, and resubmits. Application code must handle `StaleObjectStateException` (Hibernate) or equivalent
- **HTTP Layer**: `ETag` + `If-Match` headers are optimistic locking at the HTTP level — see Conditional Requests

## In Practice
Method uses optimistic locking via JPA `@Version` for all entities subject to concurrent modification in Java/Kotlin services. Conflict exceptions are caught at the service layer and translated to `409 Conflict` API responses with a message instructing the client to re-fetch. For HTTP APIs, `ETag`/`If-Match` conditional requests provide the same guarantee at the protocol level without requiring application-layer version columns.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Optimistic Locking**: Assume conflicts are rare; detect them at write time rather than preventing them with locks. Add a `version` column — include it in every UPDATE's WHERE clause. Zero rows updated = conflict; throw and retry. JPA `@Version` handles this automatically in Java/Kotlin. At the HTTP layer, `ETag` + `If-Match` is the same pattern — client sends the ETag it read; server rejects with `412` if it changed. Use pessimistic locking instead when conflicts are frequent or retrying is not practical. → `engineering-knowledge-repository/optimistic-locking.md`

## Related Entries
- [Conditional Requests](conditional-requests.md) — HTTP-native optimistic locking via ETag and If-Match headers
- [Pessimistic Locking](pessimistic-locking.md) — the alternative strategy; locks the record on read to prevent conflicts
- [Database Indexing](database-indexing.md) — the version column lookup benefits from indexing on high-traffic tables
- [CQRS](cqrs.md) — optimistic locking is commonly used on the command side of CQRS
- [Event Sourcing](event-sourcing.md) — event sourcing uses stream version numbers for the same optimistic concurrency guarantee
