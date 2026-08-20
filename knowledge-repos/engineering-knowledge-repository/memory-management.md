---
id: memory-management
tags: [pattern, performance, backend]
surfaces-at: [application-design, functional-design]
related: [profiling, connection-pooling, caching-strategies, containers]
complexity: intermediate
---

# Memory Management

## What It Is
The practices for understanding, controlling, and optimizing how applications allocate, use, and release memory. Poor memory management manifests as memory leaks (memory grows unboundedly until OOM crash), excessive garbage collection pauses (latency spikes), or over-provisioning (paying for memory that's not needed). In managed-runtime languages (Python, Java, Go, Node.js), the garbage collector handles deallocation automatically, but the GC's behavior is strongly influenced by allocation patterns — understanding GC is part of managing memory in these environments.

## When to Apply
- Services experiencing growing memory usage over time (memory leak investigation)
- Services with unexplained latency spikes (GC pause investigation)
- Container deployments where memory limits cause OOM kills
- High-throughput services where allocation rate drives GC pressure

## Key Concepts
- **Memory Leak**: Memory that is allocated but never released — references are retained longer than necessary, preventing garbage collection. Common sources:
  - Event listeners or callbacks not removed when the object is destroyed (JavaScript, Node.js)
  - Global collections (caches, registries) that grow unboundedly
  - Long-lived objects holding references to short-lived objects
  - Thread-local storage in long-running threads
  - Circular references in languages without cycle-detecting GC (Python's reference counting handles cycles, but at cost)
- **Garbage Collection Basics**:
  - *Mark and Sweep*: GC traverses all reachable objects from roots; unreachable objects are collected. Used by Go, JavaScript V8, Python (for cycles)
  - *Generational GC*: Objects are divided into generations (young/old); short-lived objects are collected frequently and cheaply; long-lived objects are promoted and collected less often. Used by JVM, .NET, Python. Key insight: most objects die young
  - *Reference Counting*: Each object tracks how many references point to it; count reaches zero → immediate collection. Simple; doesn't handle cycles. CPython uses this
- **GC Pressure**: High allocation rate → frequent GC cycles → latency spikes and CPU overhead. Reduce by:
  - Object pooling: reuse objects instead of allocating new ones for each request
  - Avoiding short-lived allocations in hot paths (avoid allocating in tight loops)
  - String interning for frequently repeated string values
  - Using value types / structs instead of heap-allocated objects where available (Go, Rust)
- **JVM Tuning**: Heap size (`-Xms`, `-Xmx`), GC algorithm (G1GC default in Java 9+; ZGC for low-latency), generation sizes. Over-small heap → frequent GC; too-large heap → long full GC pauses. Set `-Xmx` to 70-80% of container memory limit, leaving headroom for non-heap (thread stacks, native memory, metaspace)
- **Container Memory Limits**: Set Kubernetes memory limits to slightly above actual peak usage. OOM kills are silent — the container restarts with no warning logs. Add headroom for GC heap expansion and native memory. Monitor RSS (resident set size), not just heap
- **Memory Profiling Tools**:
  - Python: `tracemalloc`, `memory_profiler`, `objgraph` (visualize reference graph)
  - Node.js: `--inspect` + Chrome DevTools heap snapshot; `heapdump` for production
  - Go: `pprof` memory profile; `runtime.MemStats` for allocation stats
  - JVM: JVM Flight Recorder heap analysis; Eclipse Memory Analyzer (MAT) for heap dumps
- **Memory vs. Cache Tradeoff**: Caching reduces computation at the cost of memory. Unbounded caches become memory leaks. Always set maximum size on in-process caches (LRU eviction, TTL expiry) — `functools.lru_cache(maxsize=1000)`, Guava `CacheBuilder.maximumSize(1000)`

## In Practice
Method services set explicit Kubernetes memory limits with 30% headroom above measured peak RSS. JVM services run G1GC with heap set to 70% of container memory. Node.js services monitor heap usage via Datadog metrics and alert on heap growth trends. In-process caches use LRU eviction with bounded maximum sizes. Memory profiling (`tracemalloc` for Python, `pprof` for Go) is run quarterly on high-traffic services to detect slow-growing leaks.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Memory Management**: A memory leak that grows 1MB/hour will OOM your container in production — watch RSS trends in Datadog, not just current usage. Set Kubernetes memory limits with headroom above peak (not equal to peak) — containers at their memory limit are one request away from an OOM kill. Bound all in-process caches with a maximum size; an unbounded cache is a memory leak waiting to happen. In JVM services, tune `Xmx` to 70% of container memory — the JVM needs headroom beyond heap for metaspace, thread stacks, and GC working memory. Profile memory under realistic load before assuming a leak is under control. → `engineering-knowledge-repository/memory-management.md`

## Related Entries
- [Profiling](profiling.md) — memory profiling tools and techniques identify allocation sources and leak patterns
- [Connection Pooling](connection-pooling.md) — connection pools are a form of object pooling that reduces allocation overhead for database connections
- [Caching Strategies](caching-strategies.md) — in-process caches trade memory for computation; must be bounded to avoid leaks
- [Containers](containers.md) — container memory limits and OOM kill behavior interact directly with application memory management
