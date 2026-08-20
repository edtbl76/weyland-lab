---
id: redis-patterns
tags: [database, backend, pattern]
surfaces-at: [application-design, functional-design]
related: [caching-strategies, rate-limiting, distributed-locks, session-management, pub-sub, message-queues]
complexity: intermediate
---

# Redis Patterns

## What It Is
Common architectural patterns for using Redis — an in-memory data structure store — across different use cases in backend systems. Redis is fast (sub-millisecond operations), versatile (strings, hashes, lists, sets, sorted sets, streams, pub/sub), and widely deployed. However, each use case has specific patterns, tradeoffs, and failure modes. Treating Redis as a simple cache for all use cases misses most of its power and ignores the specific guarantees (or lack thereof) that different Redis configurations provide. Understanding Redis patterns means knowing when to use it, which data structures to use, and how to handle Redis failures gracefully.

## When to Apply
- Application-level caching to reduce database load
- Session storage for stateless application servers
- Rate limiting counters with atomic increment operations
- Distributed locking across multiple service instances
- Real-time pub/sub messaging for lightweight event broadcast
- Leaderboards, counts, and real-time analytics using sorted sets

## Key Concepts
- **Cache-Aside (Lazy Loading)**: The most common pattern. Application checks Redis first; on miss, reads from the database and populates Redis. Cache entries have TTLs; stale entries expire automatically. Tradeoff: cold cache on startup or cache miss storms
  ```
  value = redis.get(key)
  if not value:
      value = db.query(...)
      redis.setex(key, ttl=300, value=value)
  return value
  ```

- **Write-Through Cache**: On every write to the database, also write to Redis. Cache is always warm; no read misses. Tradeoff: every write has Redis overhead, including writes to data that is never read from cache

- **Rate Limiting with INCR + EXPIRE**: Atomic counter increment with TTL-based window reset. Lua scripts or `MULTI/EXEC` ensure atomicity across multiple commands:
  ```lua
  local count = redis.call('INCR', key)
  if count == 1 then redis.call('EXPIRE', key, window_seconds) end
  return count
  ```
  Sliding window rate limiting uses sorted sets: add requests with timestamp scores, remove old ones, count remaining

- **Distributed Locking (Redlock)**: `SET key value NX PX timeout` — atomic set-if-not-exists with expiry. Provides mutual exclusion across service instances. Redlock (Redis Distributed Lock) is the multi-node variant for higher safety. Important: always set a lock TTL to avoid deadlocks if the holder crashes. Don't use Redis locks for long-running critical sections — prefer database-level locking for those

- **Session Storage**: Store session data as Redis hashes (`HSET session:{id} user_id 123 expires_at 1234567890`). Set TTL equal to session timeout. Stateless application servers read session from Redis on each request. Fast; survives application restarts; supports horizontal scaling

- **Sorted Sets for Leaderboards**: `ZADD leaderboard score member` adds/updates a member's score. `ZREVRANK leaderboard member` returns rank. `ZREVRANGE leaderboard 0 9 WITHSCORES` returns top 10. Real-time leaderboards with O(log N) rank lookup

- **Pub/Sub for Lightweight Messaging**: Redis pub/sub broadcasts messages to all subscribers of a channel. At-most-once delivery (no persistence, no acknowledgement). Appropriate for: real-time notifications, cache invalidation broadcasts, lightweight event fan-out. Not appropriate for: reliable message delivery — use Kafka or SQS for that

- **Redis Streams**: A persistent, append-only log with consumer groups. Unlike pub/sub, messages are stored and can be replayed. Consumer groups allow multiple consumers to process messages with acknowledgement. Redis Streams are a lightweight Kafka alternative for lower-throughput workloads

- **Failure Handling**: Redis is a dependency; applications must handle Redis unavailability. Cache misses are expected (fall through to database). Rate limiters should fail open (allow requests) when Redis is unavailable. Session lookups should return auth failures (redirect to login) — not 500 errors

- **Memory Management**: Redis is in-memory; capacity is finite. Set `maxmemory` and an eviction policy (`allkeys-lru` for caches; `noeviction` for persistent data). Monitor `used_memory` and set alerts before hitting `maxmemory`

## In Practice
Method services use Redis for: cache-aside for database query results (TTL 60-300s), rate limiting with INCR/EXPIRE counters (per-user and per-IP), distributed locking with SET NX for background job deduplication, and session storage for web applications. Redis pub/sub is used for real-time notification broadcasting. Redis Streams are used in preference to Kafka for low-volume event pipelines where operational simplicity outweighs Kafka's durability guarantees. ElastiCache (Redis-compatible) is the managed service of choice on AWS.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Redis Patterns**: Redis is not just a cache — sorted sets, streams, and atomic operations make it a versatile building block. The most important rule: understand what Redis is authoritative for and what it isn't. Cache data should always be reconstructable from the database. Session data should handle Redis failure gracefully (re-login, not 500). Never store data in Redis that doesn't have a TTL or eviction policy — an unbounded Redis instance is a time bomb. Use Lua scripts or pipelines for multi-step atomic operations rather than multiple round trips with application-level coordination. → `engineering-knowledge-repository/redis-patterns.md`

## Related Entries
- [Caching Strategies](caching-strategies.md) — cache-aside, write-through, and other caching patterns are implemented in Redis
- [Rate Limiting](rate-limiting.md) — Redis INCR/EXPIRE is the standard implementation for in-memory rate limiting counters
- [Distributed Locks](distributed-locks.md) — Redis SET NX with TTL is the most common distributed lock implementation
- [Session Management](session-management.md) — Redis is the standard session store for horizontally-scaled stateless applications
- [Pub/Sub](pub-sub.md) — Redis pub/sub provides lightweight at-most-once message broadcast
- [Message Queues](message-queues.md) — Redis Streams offer a lightweight message queue for lower-throughput workloads
